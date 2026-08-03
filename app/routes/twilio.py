import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse

from app.config import settings
from app.db import get_db
from app.models import RendezVous, SessionChat, DisponibiliteMedecin, Patient, Resultat, DefiOtp
from app.services.otp_service import consume_otp_or_raise, generate_otp_code, compute_otp_hash, build_expiry
from app.services.upload_security import (
    build_fernet,
    decrypt_file_from_path,
    infer_content_type_from_encrypted_path,
    infer_original_extension_from_encrypted_path,
)


from app.services.reminders import notify_doctor_if_applicable
from app.services.cache import specialties_cache, slots_cache, invalidate_availabilities_cache
from app.services.auth_service import decode_appointment_token

router = APIRouter(prefix="/twilio", tags=["twilio"])

DOWNLOAD_TOKEN_TTL_MINUTES = 15


def _normalize_whatsapp_number(value: str) -> str:
    value = value.strip().replace(" ", "")
    if value.startswith("whatsapp:"):
        return value
    return f"whatsapp:{value}"


def _load_session_data(session: SessionChat) -> dict:
    if not session.donnees:
        return {}
    try:
        payload = json.loads(session.donnees)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_session(session: SessionChat, *, state: str | None = None, data: dict | None = None) -> None:
    if state is not None:
        session.etat = state
    if data is not None:
        session.donnees = json.dumps(data, ensure_ascii=False)


def _build_twiml(message: str, media_urls: list[str] | None = None) -> str:
    response = MessagingResponse()
    twiml_message = response.message()
    twiml_message.body(message)
    for media_url in media_urls or []:
        twiml_message.media(media_url)
    return str(response)


def _build_download_token(whatsapp_number: str, result_id: int, expires_at: datetime) -> str:
    payload = {
        "whatsapp_number": whatsapp_number,
        "result_id": result_id,
        "expires_at": expires_at.astimezone(timezone.utc).isoformat(),
    }
    raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(raw_payload).decode("ascii").rstrip("=")
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def _decode_download_token(token: str) -> dict:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Jeton de telechargement invalide.") from exc

    expected_signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=403, detail="Jeton de telechargement invalide.")

    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Jeton de telechargement invalide.") from exc

    return payload


def _parse_identity_input(text: str):
    text = text.strip()
    # Try splitting by comma
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) >= 3:
        last_name = parts[0]
        first_name = parts[1]
        age_str = "".join(c for c in parts[2] if c.isdigit())
        age = int(age_str) if age_str else None
        return last_name, first_name, age

    # Fallback: split by spaces
    parts = text.split()
    if len(parts) >= 3:
        # Find the part that is the age (has digits)
        age_idx = -1
        for idx, part in enumerate(parts):
            digits = "".join(c for c in part if c.isdigit())
            if digits:
                age_idx = idx
                break
        if age_idx != -1:
            age = int("".join(c for c in parts[age_idx] if c.isdigit()))
            name_parts = parts[:age_idx] + parts[age_idx+1:]
            if len(name_parts) >= 2:
                # Assume first word is first_name, rest is last_name
                return " ".join(name_parts[1:]), name_parts[0], age
            elif name_parts:
                return name_parts[0], "Sandbox", age
    return None, None, None


def _parse_results_identity_input(text: str):
    text = text.strip()
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    parts = text.split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return None, None


# build_appointment_token and decode_appointment_token are imported from app.services.auth_service


def _build_menu_message() -> str:
    return (
        "Bonjour👋🏽, Je suis Cid, votre assistant santé.\n"
        "Je suis là pour vous faciliter la vie en vous accompagnant dans vos diverses démarches médicales. Alors que puis-je faire pour vous maintenant ?\n\n"
        "Ici les différentes options :\n"
        "1. Prendre un rendez-vous\n"
        "2. Consulter mes resultats\n"
        "3. Consulter mes rendez-vous\n"
        "4. Aide / Contacter la clinique\n\n"
        "Repondez avec le chiffre choisi."
    )


def _build_results_message() -> str:
    return (
        "Un code de validation (OTP) vient de vous être envoyé par SMS pour sécuriser l'accès à vos résultats. 🔐\n"
        'Veuillez répondre avec le code reçu, ou tapez "Menu" pour revenir à l\'accueil.'
    )


def _booking_specialties(db: Session) -> list[str]:
    cached = specialties_cache.get("all")
    if cached is not None:
        return cached
    specialties = (
        db.query(DisponibiliteMedecin.specialite)
        .filter(DisponibiliteMedecin.specialite.isnot(None))
        .filter(DisponibiliteMedecin.specialite != "")
        .filter(DisponibiliteMedecin.est_disponible.is_(True), DisponibiliteMedecin.est_bloque.is_(False))
        .distinct()
        .order_by(DisponibiliteMedecin.specialite.asc())
        .all()
    )
    values = [row[0] for row in specialties if row and row[0]]
    if not values:
        values = [
            "Médecine générale",
            "Cardiologie",
            "Pédiatrie",
            "Gynécologie",
            "Dermatologie",
        ]
    specialties_cache.set("all", values)
    return values


def _format_specialty_choices(specialties: list[str]) -> str:
    lines = ["Choisissez la spécialité en répondant par le numéro ou le nom :"]
    for index, specialty in enumerate(specialties, start=1):
        lines.append(f"{index}. {specialty}")
    lines.append(f"{len(specialties) + 1}. Autre (saisir manuellement)")
    return "\n".join(lines)


def _resolve_specialty_choice(choice: str, specialties: list[str]) -> str | None:
    normalized_choice = choice.strip().lower()
    if not normalized_choice:
        return None
    # Check if "autre" is chosen by number or word
    autre_num = str(len(specialties) + 1)
    if normalized_choice == autre_num or "autre" in normalized_choice:
        return "autre"
    if normalized_choice.isdigit():
        index = int(normalized_choice) - 1
        if 0 <= index < len(specialties):
            return specialties[index]
    for specialty in specialties:
        if normalized_choice == specialty.lower():
            return specialty
    return None


def _parse_booking_date(raw_value: str):
    try:
        return datetime.strptime(raw_value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_booking_time(raw_value: str):
    try:
        return datetime.strptime(raw_value.strip(), "%H:%M").time()
    except ValueError:
        return None


def _booking_prompt(state: str, specialties: list[str] | None = None) -> str:
    if state == "booking_identity":
        return "Pourriez-vous m'indiquer votre Nom, Prénom et Âge séparés par des virgules ? (Par exemple : Dupont, Jean, 30) 😊"
    if state == "booking_phone":
        return "Sur quel numéro de téléphone le code OTP doit être envoyé ?"
    if state == "booking_specialty":
        if specialties:
            return _format_specialty_choices(specialties)
        return "Quelle spécialité souhaitez-vous consulter ?"
    if state == "booking_slot_choice":
        return "Quel créneau vous conviendrait le mieux ? Veuillez répondre avec le numéro du créneau choisi : 😊"
    if state == "booking_date":
        return "À quelle date souhaiteriez-vous prendre ce rendez-vous ? (Format : AAAA-MM-JJ, par exemple 2026-07-25) 📅"
    if state == "booking_time":
        return "Et à quelle heure ? (Format : HH:MM, par exemple 14:30) ⏰"
    return _build_menu_message()


def _find_matching_availability(
    db: Session,
    specialty: str | None,
    start_time: datetime,
) -> DisponibiliteMedecin | None:
    if not specialty:
        return None

    return (
        db.query(DisponibiliteMedecin)
        .filter(DisponibiliteMedecin.specialite == specialty)
        .filter(DisponibiliteMedecin.est_disponible.is_(True), DisponibiliteMedecin.est_bloque.is_(False))
        .filter(DisponibiliteMedecin.heure_debut == start_time)
        .order_by(DisponibiliteMedecin.heure_debut.asc())
        .with_for_update()
        .first()
    )


def _available_slots_for_specialty(db: Session, specialty: str, limit: int = 5) -> list[DisponibiliteMedecin]:
    cache_key = f"{specialty}:{limit}"
    cached = slots_cache.get(cache_key)
    if cached is not None:
        return cached
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=30)
    slots = (
        db.query(DisponibiliteMedecin)
        .filter(DisponibiliteMedecin.specialite == specialty)
        .filter(DisponibiliteMedecin.est_disponible.is_(True), DisponibiliteMedecin.est_bloque.is_(False))
        .filter(DisponibiliteMedecin.heure_debut >= now)
        .filter(DisponibiliteMedecin.heure_debut <= horizon)
        .order_by(DisponibiliteMedecin.heure_debut.asc())
        .limit(limit)
        .all()
    )
    slots_cache.set(cache_key, slots)
    return slots


def _format_slot_choices(slots: list[DisponibiliteMedecin]) -> str:
    lines = ["Créneaux disponibles :"]
    for index, slot in enumerate(slots, start=1):
        end_part = f" - {slot.heure_fin.astimezone(timezone.utc).strftime('%H:%M')}" if slot.heure_fin else ""
        lines.append(
            f"{index}. {slot.nom_medecin} | {slot.heure_debut.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')}{end_part}"
        )
    return "\n".join(lines)


def _resolve_slot_choice(choice: str, slots: list[DisponibiliteMedecin]) -> DisponibiliteMedecin | None:
    normalized_choice = choice.strip()
    if normalized_choice.isdigit():
        index = int(normalized_choice) - 1
        if 0 <= index < len(slots):
            return slots[index]
    return None


def _finalize_booking(
    db: Session,
    patient: Patient,
    booking_data: dict,
    start_time: datetime,
    background_tasks: BackgroundTasks,
    availability: DisponibiliteMedecin | None = None,
) -> RendezVous:
    specialty = booking_data.get("specialty")
    if availability is None:
        availability = _find_matching_availability(db, specialty, start_time)

    appointment = RendezVous(
        patient_id=patient.id,
        disponibilite_id=availability.id if availability is not None else None,
        demandeur_prenom=booking_data.get("first_name"),
        demandeur_nom=booking_data.get("last_name"),
        demandeur_age=booking_data.get("age"),
        numero_telephone_contact=booking_data.get("phone_number") or patient.numero_whatsapp.replace("whatsapp:", ""),
        nom_medecin=availability.nom_medecin if availability is not None else "A valider",
        specialite=specialty,
        heure_debut=start_time,
        heure_fin=availability.heure_fin if availability is not None else None,
        motif="Demande WhatsApp en attente de validation",
        statut="en_attente",
    )
    db.add(appointment)

    if booking_data.get("first_name"):
        patient.prenom = booking_data["first_name"]
    if booking_data.get("last_name"):
        patient.nom = booking_data["last_name"]

    if availability is not None:
        availability.est_disponible = False
        availability.est_bloque = True
        availability.motif_blocage = "reservation_en_attente"

    db.commit()
    db.refresh(appointment)
    invalidate_availabilities_cache()
    background_tasks.add_task(
        notify_doctor_if_applicable,
        appointment.nom_medecin,
        appointment.id,
        appointment.heure_debut,
        appointment.patient_id
    )
    return appointment


def _get_or_create_patient(db: Session, whatsapp_number: str) -> Patient:
    patient = db.query(Patient).filter(Patient.numero_whatsapp == whatsapp_number).first()
    if patient is not None:
        return patient

    if not settings.twilio_sandbox_auto_register:
        raise HTTPException(
            status_code=404,
            detail="Numero WhatsApp non enregistre. Activez TWILIO_SANDBOX_AUTO_REGISTER en sandbox ou creez le patient depuis l'interface admin.",
        )

    patient = Patient(
        numero_whatsapp=whatsapp_number,
        prenom="Sandbox",
        nom="Patient",
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/whatsapp")
def twilio_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    from_number: str = Form(..., alias="From"),
    body: str = Form("", alias="Body"),
    message_sid: str | None = Form(None, alias="MessageSid"),
    db: Session = Depends(get_db),
):
    import sys
    print(f"[TWILIO WEBHOOK] Received message from {from_number}: {body}", file=sys.stderr)
    whatsapp_number = _normalize_whatsapp_number(from_number)
    normalized_body = (body or "").strip().lower()

    patient = _get_or_create_patient(db, whatsapp_number)

    session = db.query(SessionChat).filter(SessionChat.numero_whatsapp == whatsapp_number).first()
    if session is None:
        session = SessionChat(numero_whatsapp=whatsapp_number, etat="menu", donnees=json.dumps({}, ensure_ascii=False))
        db.add(session)
        db.flush()

    session_data = _load_session_data(session)
    booking_data = session_data.get("booking")
    if not isinstance(booking_data, dict):
        booking_data = {}
        session_data["booking"] = booking_data

    if normalized_body in {"menu", "bonjour", "salut", "start", "aide"}:
        _save_session(session, state="menu", data={})
        db.commit()
        return Response(content=_build_twiml(_build_menu_message()), media_type="application/xml; charset=utf-8")

    if session.etat == "attente_otp":
        code = body.strip().replace(" ", "")
        purpose = session_data.get("purpose", "result_access")
        result_id = session_data.get("result_id")
        if result_id is None:
            _save_session(session, state="menu", data={})
            db.commit()
            return Response(
                content=_build_twiml("Session OTP invalide. Tapez Menu pour recommencer."),
                media_type="application/xml; charset=utf-8",
            )

        try:
            consume_otp_or_raise(
                db,
                secret_key=settings.secret_key,
                whatsapp_number=whatsapp_number,
                purpose=purpose,
                code=code,
            )
        except HTTPException as exc:
            return Response(content=_build_twiml(exc.detail), media_type="application/xml; charset=utf-8")

        from app.config import get_public_url
        download_expires_at = datetime.now(timezone.utc) + timedelta(minutes=DOWNLOAD_TOKEN_TTL_MINUTES)
        download_token = _build_download_token(whatsapp_number, int(result_id), download_expires_at)
        download_url = get_public_url(request, "twilio_download_result", token=download_token)

        _save_session(session, state="menu", data={})
        db.commit()
        return Response(
            content=_build_twiml(
                "OTP valide. Votre resultat est joint au message.",
                media_urls=[download_url],
            ),
            media_type="application/xml; charset=utf-8",
        )

    specialties = _booking_specialties(db)

    if session.etat == "results_identity":
        from sqlalchemy import func
        last_name, first_name = _parse_results_identity_input(body)
        if not last_name or not first_name:
            return Response(
                content=_build_twiml("Saisie invalide. Veuillez indiquer votre Nom et Prénom sous la forme : Nom, Prénom (ex: Dupont, Jean) s'il vous plaît. 😊"),
                media_type="application/xml; charset=utf-8",
            )
        
        patient_match = db.query(Patient).filter(
            ((func.lower(Patient.nom) == last_name.lower()) & (func.lower(Patient.prenom) == first_name.lower())) |
            ((func.lower(Patient.nom) == first_name.lower()) & (func.lower(Patient.prenom) == last_name.lower()))
        ).first()
        
        if not patient_match:
            return Response(
                content=_build_twiml(
                    "Désolé, aucun dossier n'est enregistré à ce nom. 😔 "
                    "Veuillez vérifier l'orthographe ou contacter la clinique. "
                    "Tapez Menu pour recommencer."
                ),
                media_type="application/xml; charset=utf-8",
            )
        
        results_data = {
            "patient_id": patient_match.id,
            "last_name": last_name,
            "first_name": first_name,
        }
        _save_session(session, state="results_phone", data={"results": results_data})
        db.commit()
        return Response(
            content=_build_twiml(
                "Veuillez renseigner le numéro pour l'envoi du SMS de confirmation.\n\n"
                "NB : Si votre numéro WhatsApp est différent de celui utilisé pour recevoir vos SMS, "
                "veuillez renseigner le numéro que vous avez communiqué à la clinique lors de votre consultation.😊"
            ),
            media_type="application/xml; charset=utf-8",
        )

    if session.etat == "results_phone":
        phone_number = body.strip()
        if not phone_number:
            return Response(
                content=_build_twiml("Merci de renseigner un numéro de téléphone valide. 😊"),
                media_type="application/xml; charset=utf-8",
            )
        
        results_data = session_data.get("results", {})
        patient_id = results_data.get("patient_id")
        if not patient_id:
            _save_session(session, state="menu", data={})
            db.commit()
            return Response(
                content=_build_twiml("Oups, la session a expiré. Tapez 'Menu' pour recommencer. 😊"),
                media_type="application/xml; charset=utf-8",
            )
            
        patient_match = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient_match:
            _save_session(session, state="menu", data={})
            db.commit()
            return Response(
                content=_build_twiml("Oups, patient introuvable. Tapez 'Menu' pour recommencer. 😊"),
                media_type="application/xml; charset=utf-8",
            )
            
        latest_result = (
            db.query(Resultat)
            .filter(Resultat.patient_id == patient_match.id)
            .order_by(Resultat.id.desc())
            .first()
        )
        if latest_result is None:
            _save_session(session, state="menu", data={})
            db.commit()
            return Response(
                content=_build_twiml("Aucun résultat n'est disponible pour le moment pour ce patient. Tapez 'Menu' pour revenir. 😊"),
                media_type="application/xml; charset=utf-8",
            )

        otp_code = generate_otp_code()
        challenge = DefiOtp(
            patient_id=patient_match.id,
            numero_whatsapp=whatsapp_number,
            objectif="result_access",
            hash_code=compute_otp_hash(
                secret_key=settings.secret_key,
                whatsapp_number=whatsapp_number,
                purpose="result_access",
                code=otp_code,
            ),
            expire_le=build_expiry(settings.otp_expiry_minutes),
            tentatives=0,
            tentatives_max=settings.otp_max_attempts,
            est_consomme=False,
        )
        db.add(challenge)
        db.commit()
        db.refresh(challenge)

        from app.services.message_gateway import get_message_gateway
        gateway = get_message_gateway()
        message_body = f"Votre code OTP pour l'accès aux résultats est: {otp_code}. Valide {settings.otp_expiry_minutes} minutes."
        try:
            gateway.send_sms(phone_number, message_body)
        except Exception:
            pass

        _save_session(
            session,
            state="attente_otp",
            data={"purpose": "result_access", "result_id": latest_result.id, "message_sid": message_sid},
        )
        db.commit()
        return Response(content=_build_twiml(_build_results_message()), media_type="application/xml; charset=utf-8")

    if session.etat == "booking_identity":
        last_name, first_name, age = _parse_identity_input(body)
        if not last_name or not first_name or age is None:
            return Response(
                content=_build_twiml(
                    "Oups, Saisie invalide. Pourriez-vous indiquer votre Nom, Prénom et Âge sous la forme : Nom, Prénom, Âge (ex: Dupont, Jean, 30) s'il vous plaît ? 😊"
                ),
                media_type="application/xml; charset=utf-8",
            )
        booking_data["last_name"] = last_name
        booking_data["first_name"] = first_name
        booking_data["age"] = age
        _save_session(session, state="booking_specialty", data={"booking": booking_data})
        db.commit()
        return Response(content=_build_twiml(_booking_prompt("booking_specialty", specialties)), media_type="application/xml; charset=utf-8")

    if session.etat == "booking_phone":
        phone_number = body.strip()
        if not phone_number:
            return Response(content=_build_twiml("Merci de saisir votre numéro de téléphone."), media_type="application/xml; charset=utf-8")
        booking_data["phone_number"] = phone_number
        _save_session(session, state="booking_specialty", data={"booking": booking_data})
        db.commit()
        return Response(content=_build_twiml(_booking_prompt("booking_specialty", specialties)), media_type="application/xml; charset=utf-8")

    if session.etat == "booking_custom_specialty":
        custom_specialty = body.strip()
        if not custom_specialty:
            return Response(content=_build_twiml("Merci de saisir la spécialité souhaitée."), media_type="application/xml; charset=utf-8")
        booking_data["specialty"] = custom_specialty
        _save_session(session, state="menu", data={})
        db.commit()
        return Response(
            content=_build_twiml(
                f"Désolé, aucun créneau n'est disponible pour la spécialité '{custom_specialty}' pour le moment.\n"
                "Tapez Menu pour revenir au choix principal."
            ),
            media_type="application/xml; charset=utf-8",
        )

    if session.etat == "booking_specialty":
        selected_specialty = _resolve_specialty_choice(body, specialties)
        if selected_specialty == "autre":
            _save_session(session, state="booking_custom_specialty", data={"booking": booking_data})
            db.commit()
            return Response(
                content=_build_twiml("Veuillez saisir le nom de la spécialité souhaitée :"),
                media_type="application/xml; charset=utf-8",
            )
        if selected_specialty is None:
            return Response(content=_build_twiml(_format_specialty_choices(specialties)), media_type="application/xml; charset=utf-8")
        booking_data["specialty"] = selected_specialty
        slots = _available_slots_for_specialty(db, selected_specialty)
        booking_data["slots"] = [
            {
                "availability_id": slot.id,
                "doctor_name": slot.nom_medecin,
                "start_time": slot.heure_debut.astimezone(timezone.utc).isoformat(),
                "end_time": slot.heure_fin.astimezone(timezone.utc).isoformat() if slot.heure_fin else None,
            }
            for slot in slots
        ]
        if slots:
            _save_session(session, state="booking_slot_choice", data={"booking": booking_data})
            db.commit()
            return Response(content=_build_twiml(_format_slot_choices(slots)), media_type="application/xml; charset=utf-8")

        _save_session(session, state="menu", data={})
        db.commit()
        return Response(
            content=_build_twiml(
                "Désolé, aucun créneau n'est disponible pour cette spécialité pour le moment.\n"
                "Tapez Menu pour revenir au choix principal."
            ),
            media_type="application/xml; charset=utf-8",
        )

    if session.etat == "booking_slot_choice":
        slots_payload = booking_data.get("slots")
        slots = []
        if isinstance(slots_payload, list):
            for slot_payload in slots_payload:
                if not isinstance(slot_payload, dict):
                    continue
                availability_id = slot_payload.get("availability_id")
                if availability_id is None:
                    continue
                slot = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == int(availability_id)).first()
                if slot is not None:
                    slots.append(slot)

        selected_slot = _resolve_slot_choice(body, slots)
        if selected_slot is not None:
            # Lock the slot to avoid concurrent booking
            locked_slot = (
                db.query(DisponibiliteMedecin)
                .filter(
                    DisponibiliteMedecin.id == selected_slot.id,
                    DisponibiliteMedecin.est_disponible.is_(True),
                    DisponibiliteMedecin.est_bloque.is_(False)
                )
                .with_for_update()
                .first()
            )
            if locked_slot is None:
                specialty = booking_data.get("specialty")
                updated_slots = _available_slots_for_specialty(db, specialty)
                booking_data["slots"] = [
                    {
                        "availability_id": s.id,
                        "doctor_name": s.nom_medecin,
                        "start_time": s.heure_debut.astimezone(timezone.utc).isoformat(),
                        "end_time": s.heure_fin.astimezone(timezone.utc).isoformat() if s.heure_fin else None,
                    }
                    for s in updated_slots
                ]
                _save_session(session, state="booking_slot_choice", data={"booking": booking_data})
                db.commit()
                
                if updated_slots:
                    return Response(
                        content=_build_twiml(
                            "Désolé, ce créneau vient d'être réservé par un autre patient. 😔\n"
                            "Veuillez choisir un autre créneau parmi les choix suivants :\n" + _format_slot_choices(updated_slots)
                        ),
                        media_type="application/xml; charset=utf-8",
                    )
                else:
                    _save_session(session, state="menu", data={})
                    db.commit()
                    return Response(
                        content=_build_twiml(
                            "Désolé, aucun créneau n'est plus disponible pour cette spécialité. 😔\n"
                            "Tapez Menu pour revenir au choix principal."
                        ),
                        media_type="application/xml; charset=utf-8",
                    )

            booking_data["availability_id"] = locked_slot.id
            booking_data["date"] = locked_slot.heure_debut.astimezone(timezone.utc).date().isoformat()
            booking_data["time"] = locked_slot.heure_debut.astimezone(timezone.utc).strftime("%H:%M")
            appointment = _finalize_booking(
                db,
                patient,
                booking_data,
                locked_slot.heure_debut,
                background_tasks,
                availability=locked_slot,
            )
            
            _save_session(session, state="menu", data={})
            db.commit()
            return Response(
                content=_build_twiml(
                    f"Merci — votre demande de rendez-vous a ete enregistree (#{appointment.id}).\n"
                    "Veuillez patienter le temps de la validation."
                ),
                media_type="application/xml; charset=utf-8",
            )

        return Response(
            content=_build_twiml(
                "Saisie invalide. " + _format_slot_choices(slots)
            ),
            media_type="application/xml; charset=utf-8",
        )

    if session.etat == "booking_date":
        requested_date = _parse_booking_date(body)
        if requested_date is None:
            return Response(content=_build_twiml("Date invalide. Répondez au format YYYY-MM-DD."), media_type="application/xml; charset=utf-8")
        if requested_date < datetime.now(timezone.utc).date():
            return Response(
                content=_build_twiml(
                    "La date de rendez-vous ne peut pas être dans le passé. Veuillez saisir une date future (format YYYY-MM-DD)."
                ),
                media_type="application/xml; charset=utf-8",
            )
        booking_data["date"] = requested_date.isoformat()
        _save_session(session, state="booking_time", data={"booking": booking_data})
        db.commit()
        return Response(content=_build_twiml(_booking_prompt("booking_time")), media_type="application/xml; charset=utf-8")

    if session.etat == "booking_time":
        requested_date_text = booking_data.get("date")
        requested_date = None
        if isinstance(requested_date_text, str):
            try:
                requested_date = datetime.strptime(requested_date_text, "%Y-%m-%d").date()
            except ValueError:
                requested_date = None

        requested_time = _parse_booking_time(body)
        if requested_date is None or requested_time is None:
            return Response(content=_build_twiml("Heure invalide. Répondez au format HH:MM."), media_type="application/xml; charset=utf-8")

        requested_start_time = datetime.combine(requested_date, requested_time, tzinfo=timezone.utc)
        if requested_start_time < datetime.now(timezone.utc):
            return Response(
                content=_build_twiml(
                    "Le créneau choisi est dans le passé. Veuillez saisir une heure future (format HH:MM)."
                ),
                media_type="application/xml; charset=utf-8",
            )
        appointment = _finalize_booking(db, patient, booking_data, requested_start_time, background_tasks)

        _save_session(session, state="menu", data={})
        db.commit()
        return Response(
            content=_build_twiml(
                f"Merci — votre demande de rendez-vous a ete enregistree (#{appointment.id}).\n"
                "Veuillez patienter le temps de la validation."
            ),
            media_type="application/xml; charset=utf-8",
        )

    if normalized_body in {"2", "resultat", "resultats", "mes resultats", "consulter mes resultats"}:
        _save_session(session, state="results_identity", data={"results": {}})
        db.commit()
        return Response(
            content=_build_twiml(
                "Veuillez indiquer votre Nom et Prénom sous la forme : Nom, Prénom (ex: Dupont, Jean) s'il vous plaît. 😊"
            ),
            media_type="application/xml; charset=utf-8",
        )

    if normalized_body.startswith("annuler"):
        parts = normalized_body.split()
        if len(parts) >= 2 and parts[1].isdigit():
            appt_id = int(parts[1])
            appt = db.query(RendezVous).filter(RendezVous.id == appt_id, RendezVous.patient_id == patient.id).first()
            if not appt:
                return Response(
                    content=_build_twiml(f"Rendez-vous #{appt_id} introuvable ou ne vous appartient pas."),
                    media_type="application/xml; charset=utf-8",
                )
            if appt.statut in {"annule", "rejete"}:
                return Response(
                    content=_build_twiml(f"Le rendez-vous #{appt_id} est déjà annulé ou rejeté."),
                    media_type="application/xml; charset=utf-8",
                )
            
            if appt.disponibilite_id is not None:
                availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == appt.disponibilite_id).first()
                if availability is not None:
                    availability.est_disponible = True
                    availability.est_bloque = False
                    availability.motif_blocage = None
            
            appt.statut = "annule"
            _save_session(session, state="menu", data={})
            db.commit()
            invalidate_availabilities_cache()
            return Response(
                content=_build_twiml(
                    f"Votre rendez-vous #{appt_id} avec le Dr {appt.nom_medecin} a été annulé avec succès et le créneau a été libéré.\n"
                    "Tapez Menu pour revenir au menu principal."
                ),
                media_type="application/xml; charset=utf-8",
            )
        else:
            return Response(
                content=_build_twiml("Pour annuler un rendez-vous, tapez : annuler <numéro_rdv> (ex: annuler 12)."),
                media_type="application/xml; charset=utf-8",
            )

    if normalized_body in {"3", "rdv", "rendez-vous", "mes rdv", "mes rendez-vous", "consulter mes rendez-vous"}:
        appointments = (
            db.query(RendezVous)
            .filter(RendezVous.patient_id == patient.id)
            .order_by(RendezVous.heure_debut.desc())
            .limit(5)
            .all()
        )
        if not appointments:
            _save_session(session, state="menu", data={})
            db.commit()
            return Response(
                content=_build_twiml(
                    "Vous n'avez aucun rendez-vous enregistré.\n"
                    "Tapez Menu pour revenir au menu principal."
                ),
                media_type="application/xml; charset=utf-8",
            )

        lines = ["Vos derniers rendez-vous :"]
        status_map = {
            "en_attente": "En attente de validation",
            "confirme": "Confirmé",
            "annule": "Annulé",
            "rejete": "Rejeté",
        }
        for appt in appointments:
            dt_str = appt.heure_debut.astimezone(timezone.utc).strftime("%d/%m/%Y à %H:%M")
            status_desc = status_map.get(appt.statut, appt.statut)
            lines.append(
                f"- [RDV #{appt.id}] Dr {appt.nom_medecin} ({appt.specialite or 'Général'}) le {dt_str} : {status_desc}"
            )
        lines.append("\nPour annuler un rendez-vous, envoyez: annuler <ID> (ex: annuler 12).")
        lines.append("Tapez Menu pour revenir au menu principal.")
        _save_session(session, state="menu", data={})
        db.commit()
        return Response(content=_build_twiml("\n".join(lines)), media_type="application/xml; charset=utf-8")

    # Handle numeric choices from the menu when in menu state
    if session.etat == "menu" and normalized_body in {"1", "4"}:
        if normalized_body == "1":
            _save_session(session, state="booking_identity", data={"booking": {}})
            db.commit()
            return Response(
                content=_build_twiml(
                    _booking_prompt("booking_identity")
                ),
                media_type="application/xml; charset=utf-8",
            )

        if normalized_body == "4":
            return Response(
                content=_build_twiml(
                    "Contact clinique : Tel +33 1 23 45 67 89\nEmail : contact@clinique.example\nTapez Menu pour revenir au menu principal."
                ),
                media_type="application/xml; charset=utf-8",
            )

    if session.etat == "menu":
        db.commit()
        return Response(content=_build_twiml(_build_menu_message()), media_type="application/xml; charset=utf-8")

    _save_session(session, state="menu", data={})
    db.commit()
    return Response(content=_build_twiml(_build_menu_message()), media_type="application/xml; charset=utf-8")


@router.get("/download/{token}", name="twilio_download_result")
def twilio_download_result(token: str, db: Session = Depends(get_db)):
    payload = _decode_download_token(token)
    whatsapp_number = payload.get("whatsapp_number")
    result_id = payload.get("result_id")
    expires_at_raw = payload.get("expires_at")

    if not whatsapp_number or result_id is None or not expires_at_raw:
        raise HTTPException(status_code=400, detail="Jeton de telechargement incomplet.")

    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Jeton de telechargement invalide.") from exc

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Lien de telechargement expire.")

    patient = db.query(Patient).filter(Patient.numero_whatsapp == whatsapp_number).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable.")

    result = db.query(Resultat).filter(Resultat.id == int(result_id), Resultat.patient_id == patient.id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Resultat introuvable.")

    fernet = build_fernet(settings.fernet_key)
    decrypted_bytes = decrypt_file_from_path(result.chemin_fichier, fernet)

    extension = infer_original_extension_from_encrypted_path(result.chemin_fichier)
    media_type = infer_content_type_from_encrypted_path(result.chemin_fichier)
    filename = f"result_{result.id}{extension}"

    return Response(
        content=decrypted_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/download-appointment/{token}", name="twilio_download_appointment")
def twilio_download_appointment(token: str, db: Session = Depends(get_db)):
    payload = decode_appointment_token(token)
    whatsapp_number = payload.get("whatsapp_number")
    appointment_id = payload.get("appointment_id")
    expires_at_raw = payload.get("expires_at")

    if not whatsapp_number or appointment_id is None or not expires_at_raw:
        raise HTTPException(status_code=400, detail="Jeton de téléchargement incomplet.")

    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Jeton de téléchargement invalide.") from exc

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Lien de téléchargement expiré.")

    patient = db.query(Patient).filter(Patient.numero_whatsapp == whatsapp_number).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable.")

    appointment = db.query(RendezVous).filter(RendezVous.id == int(appointment_id), RendezVous.patient_id == patient.id).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable.")

    from app.services.pdf_generator import generate_appointment_pdf
    pdf_bytes = generate_appointment_pdf(
        patient_name=f"{patient.prenom} {patient.nom}",
        patient_id=patient.id,
        patient_whatsapp=patient.numero_whatsapp,
        appointment_id=appointment.id,
        doctor_name=appointment.nom_medecin,
        specialty=appointment.specialite or "Médecine générale",
        appointment_date=appointment.heure_debut.astimezone(timezone.utc).strftime("%d/%m/%Y"),
        appointment_time=appointment.heure_debut.astimezone(timezone.utc).strftime("%H:%M"),
    )

    filename = f"rendez_vous_{appointment.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )