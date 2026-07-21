from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.orm import Session

from app.models import RendezVous
from app.services.message_gateway import get_message_gateway

logger = logging.getLogger(__name__)


def send_upcoming_appointment_reminders(db: Session) -> int:
    """Find confirmed appointments scheduled in 23-25 hours and send WhatsApp reminders."""
    now = datetime.now(timezone.utc)
    lower_bound = now + timedelta(hours=23)
    upper_bound = now + timedelta(hours=25)

    logger.info("Checking for reminders in range: %s to %s", lower_bound, upper_bound)

    appointments = (
        db.query(RendezVous)
        .filter(
            RendezVous.statut == "confirme",
            RendezVous.rappel_envoye == False,
            RendezVous.heure_debut >= lower_bound,
            RendezVous.heure_debut <= upper_bound,
        )
        .all()
    )

    sent_count = 0
    gateway = get_message_gateway()

    for appt in appointments:
        patient = appt.patient
        if not patient or not patient.numero_whatsapp:
            logger.warning("Appointment #%d has no patient or patient WhatsApp number", appt.id)
            continue

        # Format start time beautifully in UTC/local timezone representation
        dt_str = appt.heure_debut.astimezone(timezone.utc).strftime("%d/%m/%Y à %H:%M")
        body = (
            f"Rappel de votre rendez-vous : Vous avez rendez-vous avec le Dr {appt.nom_medecin} "
            f"({appt.specialite or 'Général'}) le {dt_str}."
        )

        try:
            logger.info("Sending reminder WhatsApp to %s for appointment #%d", patient.numero_whatsapp, appt.id)
            gateway.send_whatsapp(patient.numero_whatsapp, body)
            appt.rappel_envoye = True
            sent_count += 1
        except Exception:
            logger.exception("Failed to send reminder WhatsApp for appointment #%d", appt.id)

    if sent_count > 0:
        db.commit()

    return sent_count


def check_and_send_doctor_reminders(db: Session) -> int:
    """Find doctor users with no future availability slots and send reminders (WhatsApp and/or email).

    Checks history to ensure only one reminder is sent per doctor per week.
    """
    import json
    from datetime import datetime, timedelta, timezone
    from app.models import Utilisateur, DisponibiliteMedecin, JournalMessage

    # Get all doctor users
    doctors = db.query(Utilisateur).filter(Utilisateur.role == "doctor").all()

    # Get all future slots
    now = datetime.now(timezone.utc)
    future_slots = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.heure_debut >= now).all()

    # Map future slots to clean doctor names
    doctor_slots_count = {}
    for slot in future_slots:
        if not slot.nom_medecin:
            continue
        clean_slot_doc = slot.nom_medecin.lower().replace("dr.", "").replace("dr", "").replace(" ", "").replace("_", "").strip()
        doctor_slots_count[clean_slot_doc] = doctor_slots_count.get(clean_slot_doc, 0) + 1

    reminders_sent = 0
    gateway = get_message_gateway()
    one_week_ago = now - timedelta(days=7)

    for doc in doctors:
        clean_username = doc.nom_utilisateur.lower().replace("dr.", "").replace("dr", "").replace(" ", "").replace("_", "").strip()

        # Check if doctor has any future slots
        slots_count = 0
        for clean_slot_doc, count in doctor_slots_count.items():
            if clean_username in clean_slot_doc or clean_slot_doc in clean_username:
                slots_count += count

        if slots_count == 0:
            # Check if we already sent a reminder in the last 7 days to either phone or email
            destinations = []
            if doc.numero_telephone:
                destinations.append(doc.numero_telephone)
            if doc.email:
                destinations.append(doc.email)

            if not destinations:
                continue

            already_sent = (
                db.query(JournalMessage)
                .filter(
                    JournalMessage.numero_destinataire.in_(destinations),
                    JournalMessage.corps.like("%Rappel Docteur%"),
                    JournalMessage.cree_le >= one_week_ago,
                )
                .first()
            )
            if already_sent:
                logger.info("Doctor reminder already sent to %s in the last 7 days", doc.nom_utilisateur)
                continue

            body = (
                f"Rappel Docteur : Bonjour Dr {doc.nom_utilisateur}, vous n'avez aucun créneau "
                f"de consultation enregistré sur Cid pour les jours à venir. "
                f"Merci de vous connecter sur l'interface pour renseigner vos disponibilités."
            )

            sent_via_whatsapp = False
            if doc.numero_telephone:
                try:
                    gateway.send_whatsapp(doc.numero_telephone, body)
                    sent_via_whatsapp = True
                except Exception as e:
                    logger.warning("Failed to send WhatsApp slot reminder to %s: %s", doc.nom_utilisateur, e)

            sent_via_email = False
            if doc.email:
                email_record = {
                    "to": doc.email,
                    "subject": "Rappel Cid : Renseigner vos créneaux de consultation",
                    "body": body,
                    "ts": datetime.now(timezone.utc).isoformat() + "Z",
                }
                try:
                    with open("email_simulation.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps(email_record, ensure_ascii=False) + "\n")

                    db_record = JournalMessage(
                        numero_destinataire=doc.email,
                        corps=body,
                        urls_media=json.dumps([]),
                        via="email",
                        sid_externe=f"email-stub-{int(datetime.now(timezone.utc).timestamp())}",
                        statut="envoye",
                        tentatives=1,
                    )
                    db.add(db_record)
                    db.commit()
                    sent_via_email = True
                except Exception as e:
                    logger.warning("Failed to log email slot reminder to %s: %s", doc.nom_utilisateur, e)

            if sent_via_whatsapp or sent_via_email:
                reminders_sent += 1

    return reminders_sent


def start_doctor_reminder_scheduler():
    import threading
    import time
    from app.db import SessionLocal

    def run_scheduler():
        logger.info("Doctor slot reminders background scheduler started.")
        time.sleep(10) # wait 10 seconds for startup
        while True:
            try:
                now = datetime.now(timezone.utc)
                if now.weekday() == 4 and now.hour == 14:
                    logger.info("It is Friday 14h UTC. Running doctor reminders background task.")
                    db = SessionLocal()
                    try:
                        count = check_and_send_doctor_reminders(db)
                        logger.info("Scheduler sent %d reminders successfully.", count)
                    finally:
                        db.close()
            except Exception:
                logger.exception("Error in run_scheduler loop")
            
            time.sleep(3600)

    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()
