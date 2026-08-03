from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RendezVous, DisponibiliteMedecin, Patient, Utilisateur
from app.schemas import RendezVousCreate, RendezVousOut, RendezVousUpdate
from app.services.auth_service import require_user, log_activity
from app.services.reminders import send_upcoming_appointment_reminders, notify_doctor_if_applicable
from app.services.cache import invalidate_availabilities_cache

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _attach_availability_fields(appointment: RendezVous, payload: RendezVousCreate | RendezVousUpdate):
    if payload.nom_medecin is not None:
        appointment.nom_medecin = payload.nom_medecin
    if payload.specialite is not None:
        appointment.specialite = payload.specialite
    if payload.demandeur_prenom is not None:
        appointment.demandeur_prenom = payload.demandeur_prenom
    if payload.demandeur_nom is not None:
        appointment.demandeur_nom = payload.demandeur_nom
    if payload.demandeur_age is not None:
        appointment.demandeur_age = payload.demandeur_age
    if payload.numero_telephone_contact is not None:
        appointment.numero_telephone_contact = payload.numero_telephone_contact
    if payload.heure_debut is not None:
        appointment.heure_debut = payload.heure_debut
    if payload.heure_fin is not None:
        appointment.heure_fin = payload.heure_fin
    if hasattr(payload, "motif") and payload.motif is not None:
        appointment.motif = payload.motif


# notify_doctor_if_applicable is imported from app.services.reminders


@router.post("", response_model=RendezVousOut, status_code=201)
def create_appointment(
    payload: RendezVousCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    if payload.patient_id is None:
        raise HTTPException(status_code=400, detail="patient_id est requis pour créer un rendez-vous.")
    
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable.")

    selected_availability = None
    if payload.disponibilite_id is not None:
        selected_availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == payload.disponibilite_id).with_for_update().first()
        if selected_availability is None:
            raise HTTPException(status_code=404, detail="Creneau introuvable.")
        if not selected_availability.est_disponible or selected_availability.est_bloque:
            raise HTTPException(status_code=409, detail="Creneau deja pris ou bloque.")

        if payload.nom_medecin and payload.nom_medecin != selected_availability.nom_medecin:
            raise HTTPException(status_code=400, detail="Le medecin ne correspond pas au creneau choisi.")
        if payload.specialite and selected_availability.specialite and payload.specialite != selected_availability.specialite:
            raise HTTPException(status_code=400, detail="La specialite ne correspond pas au creneau choisi.")

    appointment = RendezVous(
        patient_id=payload.patient_id,
        disponibilite_id=payload.disponibilite_id,
        demandeur_prenom=payload.demandeur_prenom,
        demandeur_nom=payload.demandeur_nom,
        demandeur_age=payload.demandeur_age,
        numero_telephone_contact=payload.numero_telephone_contact,
        nom_medecin=payload.nom_medecin,
        specialite=payload.specialite,
        heure_debut=payload.heure_debut,
        heure_fin=payload.heure_fin,
        motif=payload.motif,
        statut="en_attente",
    )
    db.add(appointment)

    if selected_availability is not None:
        selected_availability.est_disponible = False
        selected_availability.est_bloque = True
        selected_availability.motif_blocage = "reserve"

    db.commit()
    db.refresh(appointment)
    
    background_tasks.add_task(
        notify_doctor_if_applicable,
        appointment.nom_medecin,
        appointment.id,
        appointment.heure_debut,
        appointment.patient_id
    )
    invalidate_availabilities_cache()
    
    log_activity(db, current_user.nom_utilisateur, f"Création administrative du rendez-vous #{appointment.id} avec le Dr {appointment.nom_medecin} pour le patient #{payload.patient_id}")
    
    return appointment


@router.get("", response_model=list[RendezVousOut])
def list_appointments(
    patient_id: int | None = Query(default=None),
    doctor_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    query = db.query(RendezVous)
    if patient_id is not None:
        query = query.filter(RendezVous.patient_id == patient_id)
    if doctor_name is not None:
        query = query.filter(RendezVous.nom_medecin == doctor_name)
    if status is not None:
        query = query.filter(RendezVous.statut == status)
    return query.order_by(RendezVous.heure_debut.asc()).all()


@router.get("/{appointment_id}", response_model=RendezVousOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    appointment = db.query(RendezVous).filter(RendezVous.id == appointment_id).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable.")
    return appointment


def send_whatsapp_in_background(to_number: str, body: str, media_urls: list[str] | None = None):
    from app.services.message_gateway import get_message_gateway
    gateway = get_message_gateway()
    try:
        gateway.send_whatsapp(to_number, body, media_urls=media_urls)
    except Exception:
        pass


@router.patch("/{appointment_id}", response_model=RendezVousOut)
def update_appointment(
    appointment_id: int,
    payload: RendezVousUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    appointment = db.query(RendezVous).filter(RendezVous.id == appointment_id).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable.")

    previous_status = appointment.statut
    previous_availability_id = appointment.disponibilite_id
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(appointment, key, value)

    if appointment.statut == "confirme" and previous_status != "confirme" and appointment.disponibilite_id is not None:
        availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == appointment.disponibilite_id).first()
        if availability is not None:
            availability.est_disponible = False
            availability.est_bloque = True
            availability.motif_blocage = "confirme"

    if appointment.statut in {"rejete", "annule"} and previous_availability_id is not None:
        availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == previous_availability_id).first()
        if availability is not None:
            availability.est_disponible = True
            availability.est_bloque = False
            availability.motif_blocage = None

    db.commit()
    db.refresh(appointment)

    # Send confirmation WhatsApp message with PDF summary if the status transitioned to 'confirme'
    if appointment.statut == "confirme" and previous_status != "confirme":
        patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
        if patient is not None:
            from app.services.auth_service import build_appointment_token
            from app.config import get_public_url
            from datetime import datetime, timedelta
            
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            token = build_appointment_token(patient.numero_whatsapp, appointment.id, expires_at)
            download_url = get_public_url(request, "twilio_download_appointment", token=token)
            
            dt_str = appointment.heure_debut.astimezone(timezone.utc).strftime("%d/%m/%Y à %H:%M")
            msg_body = (
                f"Votre rendez-vous avec le Dr {appointment.nom_medecin} ({appointment.specialite or 'Général'}) "
                f"le {dt_str} a été validé et confirmé par la clinique.\n"
                f"Vous trouverez votre fiche récapitulative officielle (PDF) ci-jointe."
            )
            background_tasks.add_task(
                send_whatsapp_in_background,
                patient.numero_whatsapp,
                msg_body,
                [download_url]
            )
    
    invalidate_availabilities_cache()
    log_activity(db, current_user.nom_utilisateur, f"Modification du rendez-vous #{appointment.id} (nouveau statut: {appointment.statut})")
    
    return appointment


@router.delete("/{appointment_id}", status_code=204)
def delete_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    appointment = db.query(RendezVous).filter(RendezVous.id == appointment_id).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable.")

    availability = None
    if appointment.disponibilite_id is not None:
        availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == appointment.disponibilite_id).first()

    db.delete(appointment)
    if availability is not None:
        availability.est_disponible = True
        availability.est_bloque = False
        availability.motif_blocage = None

    db.commit()
    invalidate_availabilities_cache()
    
    log_activity(db, current_user.nom_utilisateur, f"Suppression du rendez-vous #{appointment_id}")
    
    return None


@router.post("/send-reminders")
def trigger_reminders(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé. Administrateur uniquement.")
    
    count = send_upcoming_appointment_reminders(db)
    return {"message": f"{count} rappels envoyés avec succès."}
