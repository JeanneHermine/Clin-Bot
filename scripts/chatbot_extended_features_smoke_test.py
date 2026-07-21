import os
import sys
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Dev overrides
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["OTP_DEBUG_RETURN_CODE"] = "true"

from app.main import app
from app.db import SessionLocal
from app.models import Patient, RendezVous, DisponibiliteMedecin, Utilisateur, JournalMessage
from scripts.test_support import cleanup_test_data


def main() -> None:
    client = TestClient(app)
    db = SessionLocal()

    # Pre-clean
    cleanup_test_data(db, whatsapp_prefix="whatsapp:+999999")
    # Delete test users
    db.query(Utilisateur).filter(Utilisateur.nom_utilisateur.like("dr_smoke%")).delete()
    db.commit()

    # Login as admin to perform API requests
    login_resp = client.post("/admin/login", json={"nom_utilisateur": "admin", "mot_de_passe": "admin"})
    if login_resp.status_code != 200:
        raise RuntimeError("Failed to log in as admin for test setup")

    # Setup patient
    whatsapp_number = "whatsapp:+9999990033"
    patient_payload = {
        "numero_whatsapp": whatsapp_number,
        "prenom": "Extended",
        "nom": "Test",
        "date_naissance": "1990-05-15",
    }
    resp = client.post("/patients", json=patient_payload)
    if resp.status_code != 201:
        raise RuntimeError("Failed to create patient")
    patient_id = resp.json()["id"]

    try:
        # Setup doctor user with phone number
        doctor_phone = "whatsapp:+9999990044"
        hashed_pw = "notreal"
        doc_user = Utilisateur(
            nom_utilisateur="dr_smoketest",
            mot_de_passe_hashe=hashed_pw,
            role="doctor",
            numero_telephone=doctor_phone,
        )
        db.add(doc_user)
        db.commit()
        db.refresh(doc_user)

        # 1) Setup availability for doctor
        av_start = datetime.now(timezone.utc) + timedelta(days=1)
        availability = DisponibiliteMedecin(
            nom_medecin="Dr Smoke Test",
            specialite="Cardiologie",
            heure_debut=av_start,
            heure_fin=av_start + timedelta(hours=1),
            est_disponible=True,
            est_bloque=False,
        )
        db.add(availability)
        db.commit()
        db.refresh(availability)

        # 2) Test chatbot validation of identity prompt
        client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "1"}) # option 1 booking
        
        # Saisir une identité invalide
        invalid_identity = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "Extended Test"})
        if "Saisie invalide" not in invalid_identity.text:
            raise RuntimeError(f"Expected identity validation error, got: {invalid_identity.text}")

        # Saisir une identité valide
        client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "Test, Extended, 36"})
        
        # Choisir la spécialité (Cardiologie) - Le numéro de téléphone n'est plus demandé
        specialty_resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "1"})
        
        # 3) Test chatbot booking request and doctor notification
        # Choose the available slot (Option 1)
        booking_confirm_resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "1"})
        if "enregistree" not in booking_confirm_resp.text:
            raise RuntimeError(f"Failed to book slot: {booking_confirm_resp.text}")
        if "download-appointment" in booking_confirm_resp.text:
            raise RuntimeError(f"PDF should not be attached on initial booking request: {booking_confirm_resp.text}")

        # Verify doctor notification log exists in database
        doc_notification = db.query(JournalMessage).filter(JournalMessage.numero_destinataire == doctor_phone).first()
        if not doc_notification or "Notification Docteur" not in doc_notification.corps:
            raise RuntimeError("Doctor notification was not sent/logged")

        # Get the booked appointment ID
        appt = db.query(RendezVous).filter(RendezVous.patient_id == patient_id).order_by(RendezVous.id.desc()).first()
        appt_id = appt.id

        # Confirm the appointment via the PATCH API as the logged-in admin user
        confirm_resp = client.patch(f"/appointments/{appt_id}", json={"statut": "confirme"})
        if confirm_resp.status_code != 200:
            raise RuntimeError(f"Failed to confirm appointment via API: {confirm_resp.status_code} {confirm_resp.text}")

        # Check that the WhatsApp confirmation message was sent/logged via the gateway (containing the download URL)
        confirmation_log = db.query(JournalMessage).filter(
            JournalMessage.numero_destinataire == whatsapp_number, 
            JournalMessage.corps.like("%confirmé%"),
            JournalMessage.urls_media.like("%download-appointment%")
        ).first()
        if not confirmation_log:
            raise RuntimeError("Appointment confirmation message with PDF was not logged in DB")

        # 4) Test Cancellation via chatbot
        # View appointments first
        list_resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "3"})
        if f"RDV #{appt_id}" not in list_resp.text or "annuler &lt;ID&gt;" not in list_resp.text:
            raise RuntimeError(f"Expected RDV info and cancel instruction, got:\n{list_resp.text}")

        # Send cancellation request
        cancel_resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": f"annuler {appt_id}"})
        if "annulé avec succès" not in cancel_resp.text:
            raise RuntimeError(f"Failed to cancel appointment: {cancel_resp.text}")

        # Check in DB
        db.refresh(appt)
        if appt.statut != "annule":
            raise RuntimeError(f"Expected cancelled status in DB, got: {appt.statut}")

        db.refresh(availability)
        if not availability.est_disponible or availability.est_bloque:
            raise RuntimeError("Expected slot to be released")

        # 5) Test Automatic Reminders
        # Create a confirmed appointment scheduled exactly 24 hours in the future
        appt2_start = datetime.now(timezone.utc) + timedelta(hours=24)
        availability2 = DisponibiliteMedecin(
            nom_medecin="Dr Smoke Test",
            specialite="Cardiologie",
            heure_debut=appt2_start,
            heure_fin=appt2_start + timedelta(hours=1),
            est_disponible=False,
            est_bloque=True,
        )
        db.add(availability2)
        db.commit()

        appt2 = RendezVous(
            patient_id=patient_id,
            disponibilite_id=availability2.id,
            demandeur_prenom="Extended",
            demandeur_nom="Test",
            demandeur_age=36,
            numero_telephone_contact="+9999990033",
            nom_medecin="Dr Smoke Test",
            specialite="Cardiologie",
            heure_debut=appt2_start,
            heure_fin=appt2_start + timedelta(hours=1),
            statut="confirme",
            rappel_envoye=False,
        )
        db.add(appt2)
        db.commit()

        # Run send reminders via trigger endpoint (requires admin auth)
        # Authenticate admin session or bypass auth using settings.otp_debug_return_code (active)
        trigger_resp = client.post("/appointments/send-reminders")
        if trigger_resp.status_code != 200:
            raise RuntimeError(f"Trigger reminders endpoint failed: {trigger_resp.status_code} {trigger_resp.text}")
        
        # Verify database update
        db.refresh(appt2)
        if not appt2.rappel_envoye:
            raise RuntimeError("Expected reminder_sent to be True after sending")

        # Verify WhatsApp reminder log exists
        reminder_log = db.query(JournalMessage).filter(JournalMessage.numero_destinataire == whatsapp_number, JournalMessage.corps.like("%Rappel%")).first()
        if not reminder_log:
            raise RuntimeError("WhatsApp reminder log not found in database")

        print("Chatbot extended features smoke test OK")

    finally:
        db.close()
        # Clean up
        db_cleanup = SessionLocal()
        cleanup_test_data(db_cleanup, whatsapp_prefix="whatsapp:+999999")
        db_cleanup.query(Utilisateur).filter(Utilisateur.nom_utilisateur.like("dr_smoke%")).delete()
        db_cleanup.commit()
        db_cleanup.close()


if __name__ == "__main__":
    main()
