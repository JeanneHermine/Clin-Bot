import os
import sys
import json
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Ensure dev/testing overrides
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["OTP_DEBUG_RETURN_CODE"] = "true"

from app.main import app
from app.db import SessionLocal
from app.models import Patient, RendezVous, DisponibiliteMedecin, JournalMessage, Utilisateur, SessionChat
from app.services.cache import specialties_cache, slots_cache, invalidate_availabilities_cache
from scripts.test_support import cleanup_test_data

def set_session_for_booking_slot(db, whatsapp_number, availability):
    session = db.query(SessionChat).filter(SessionChat.numero_whatsapp == whatsapp_number).first()
    if not session:
        session = SessionChat(numero_whatsapp=whatsapp_number)
        db.add(session)
    session.etat = "booking_slot_choice"
    session.donnees = json.dumps({
        "booking": {
            "first_name": "Opt",
            "last_name": "Test",
            "age": 30,
            "phone_number": "+9999990044",
            "specialty": availability.specialite,
            "slots": [
                {
                    "availability_id": availability.id,
                    "doctor_name": availability.nom_medecin,
                    "start_time": availability.heure_debut.astimezone(timezone.utc).isoformat(),
                    "end_time": availability.heure_fin.astimezone(timezone.utc).isoformat() if availability.heure_fin else None,
                }
            ]
        }
    })
    db.commit()

def main():
    client = TestClient(app)
    db = SessionLocal()

    # Pre-clean test data
    cleanup_test_data(db, whatsapp_prefix="whatsapp:+999999")
    # Clean message logs with these test numbers too
    db.query(JournalMessage).filter(JournalMessage.numero_destinataire.like("%999999%")).delete(synchronize_session=False)
    db.query(Utilisateur).filter(Utilisateur.nom_utilisateur.like("Dr Smoke Test%")).delete(synchronize_session=False)
    db.query(SessionChat).filter(SessionChat.numero_whatsapp.like("%999999%")).delete(synchronize_session=False)
    db.commit()

    # 1) Setup patient
    whatsapp_number = "whatsapp:+9999990044"
    patient_payload = {
        "numero_whatsapp": whatsapp_number,
        "prenom": "Opt",
        "nom": "Test",
        "date_naissance": "1990-05-15",
    }
    
    # Login to do patient creation API
    from app.services.auth_service import hash_password
    admin = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "admin").first()
    if not admin:
        admin = Utilisateur(nom_utilisateur="admin", mot_de_passe_hashe=hash_password("admin"), role="admin")
        db.add(admin)
        db.commit()
    
    resp_login = client.post("/admin/login", json={"nom_utilisateur": "admin", "mot_de_passe": "admin"})
    if resp_login.status_code != 200:
         raise RuntimeError("Failed to login as admin for setup")

    resp = client.post("/patients", json=patient_payload)
    assert resp.status_code == 201, f"Failed to create patient: {resp.text}"
    patient_id = resp.json()["id"]

    try:
        # Create a doctor user for notification
        doctor_user = Utilisateur(
            nom_utilisateur="Dr Smoke Test Opt",
            mot_de_passe_hashe="fake-hash",
            role="doctor",
            numero_telephone="whatsapp:+9999990055",
        )
        db.add(doctor_user)
        db.commit()

        # Add doctor availability slot
        availability = DisponibiliteMedecin(
            nom_medecin="Dr Smoke Test Opt",
            specialite="Cardiologie",
            heure_debut=datetime.now(timezone.utc) + timedelta(days=5),
            heure_fin=datetime.now(timezone.utc) + timedelta(days=5, hours=1),
            est_disponible=True,
            est_bloque=False,
        )
        db.add(availability)
        db.commit()
        db.refresh(availability)

        print("--- PHASE 1: Testing Cache Invalidation & Persistence ---")
        # Ensure caches are initially clear or clear them manually
        invalidate_availabilities_cache()
        assert not specialties_cache.cache, "Specialties cache should be empty"
        assert not slots_cache.cache, "Slots cache should be empty"

        # Setup session state to request specialties
        session = SessionChat(numero_whatsapp=whatsapp_number, etat="booking_specialty", donnees="{}")
        db.add(session)
        db.commit()

        # Webhook call for specialty "Cardiologie" -> triggers slots lookup and queries specialties
        resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "Cardiologie"})
        assert resp.status_code == 200

        # specialties and slots cache should now have cached values
        assert "all" in specialties_cache.cache, "Specialties cache should contain 'all' key"
        cached_specialties = specialties_cache.get("all")
        assert "Cardiologie" in cached_specialties, "Cardiologie should be in cached specialties"
        assert len(slots_cache.cache) > 0, "Slots cache should contain keys"

        # Modify availability directly to trigger cache invalidation
        invalidate_availabilities_cache()
        assert not specialties_cache.cache, "Specialties cache should be empty after invalidation"
        assert not slots_cache.cache, "Slots cache should be empty after invalidation"
        print("Phase 1 Cache OK")

        print("--- PHASE 2: Testing BackgroundTasks for Doctor Notifications ---")
        # Clear log table of any previous test entries
        db.query(JournalMessage).filter(JournalMessage.numero_destinataire == "whatsapp:+9999990055").delete()
        db.commit()

        # Re-verify availability is available
        availability.est_disponible = True
        availability.est_bloque = False
        db.commit()

        # Direct setup of session at slot confirmation state
        set_session_for_booking_slot(db, whatsapp_number, availability)

        # Confirm booking via Webhook
        resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "1"})
        assert resp.status_code == 200
        assert "enregistree" in resp.text

        # The webhook response should return immediately. Let's check if the doctor received a notification in JournalMessage
        logs = db.query(JournalMessage).filter(JournalMessage.numero_destinataire == "whatsapp:+9999990055").all()
        assert len(logs) == 1, f"Expected 1 notification log for doctor, got {len(logs)}"
        assert logs[0].statut == "envoye", f"Expected statut 'envoye', got {logs[0].statut}"
        assert logs[0].tentatives == 1
        print("Phase 2 BackgroundTasks OK")

        print("--- PHASE 3: Testing Outbox Pattern & Resend Script ---")
        # Let's delete previous logs for the test numbers
        db.query(JournalMessage).filter(JournalMessage.numero_destinataire.like("%999999%")).delete()
        db.commit()

        # Create doctor user with "fail" or "555" in phone number
        doctor_user_fail = Utilisateur(
            nom_utilisateur="Dr Smoke Test Fail",
            mot_de_passe_hashe="fake-hash",
            role="doctor",
            numero_telephone="whatsapp:+9999990555", # ends with 555, triggers simulated failure
        )
        db.add(doctor_user_fail)
        db.commit()

        availability_fail = DisponibiliteMedecin(
            nom_medecin="Dr Smoke Test Fail",
            specialite="Cardiologie",
            heure_debut=datetime.now(timezone.utc) + timedelta(days=6),
            heure_fin=datetime.now(timezone.utc) + timedelta(days=6, hours=1),
            est_disponible=True,
            est_bloque=False,
        )
        db.add(availability_fail)
        db.commit()
        db.refresh(availability_fail)

        # Direct setup of session at slot confirmation state for failing slot
        set_session_for_booking_slot(db, whatsapp_number, availability_fail)

        # Confirm booking
        resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "1"})
        assert resp.status_code == 200

        # Verify failed log is created
        db.expire_all()
        failed_logs = db.query(JournalMessage).filter(JournalMessage.numero_destinataire == "whatsapp:+9999990555").all()
        assert len(failed_logs) == 1, f"Expected 1 failed log for failing doctor, got {len(failed_logs)}"
        assert failed_logs[0].statut == "echoue"
        assert failed_logs[0].tentatives == 1

        # Run outbox retry (expect 0 successful resends)
        from app.services.outbox import retry_failed_messages
        success_count = retry_failed_messages(db)
        assert success_count == 0, f"Expected 0 successful resends, got {success_count}"

        db.refresh(failed_logs[0])
        assert failed_logs[0].tentatives == 2
        assert failed_logs[0].statut == "echoue"

        # Update number to a safe number and run retry process
        failed_log = failed_logs[0]
        failed_log.numero_destinataire = "whatsapp:+9999990066"
        db.commit()

        success_count = retry_failed_messages(db)
        assert success_count == 1, f"Expected 1 successful resend, got {success_count}"

        db.refresh(failed_log)
        assert failed_log.statut == "envoye"
        assert failed_log.tentatives == 3
        print("Phase 3 Outbox retry OK")

    finally:
        db.close()
        db_cleanup = SessionLocal()
        db_cleanup.query(JournalMessage).filter(JournalMessage.numero_destinataire.like("%999999%")).delete(synchronize_session=False)
        db_cleanup.query(Utilisateur).filter(Utilisateur.nom_utilisateur.like("Dr Smoke Test%")).delete(synchronize_session=False)
        db_cleanup.query(SessionChat).filter(SessionChat.numero_whatsapp.like("%999999%")).delete(synchronize_session=False)
        db_cleanup.commit()
        cleanup_test_data(db_cleanup, whatsapp_prefix="whatsapp:+999999")
        db_cleanup.close()
        print("Cleanup completed successfully.")

if __name__ == "__main__":
    main()
    print("Chatbot optimizations smoke test PASSED")
