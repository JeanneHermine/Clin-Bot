import os
import sys
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
from app.models import Patient, RendezVous, DisponibiliteMedecin
from scripts.test_support import cleanup_test_data


def main() -> None:
    client = TestClient(app)
    db = SessionLocal()

    # 1) Setup patient
    whatsapp_number = "whatsapp:+9999990033"
    patient_payload = {
        "numero_whatsapp": whatsapp_number,
        "prenom": "Chatbot",
        "nom": "Test",
        "date_naissance": "1990-05-15",
    }
    
    # Pre-clean just in case
    cleanup_test_data(db, whatsapp_prefix="whatsapp:+999999")

    # Login as admin to perform API requests
    login_resp = client.post("/admin/login", json={"nom_utilisateur": "admin", "mot_de_passe": "admin"})
    if login_resp.status_code != 200:
        raise RuntimeError("Failed to log in as admin for test setup")

    # Create patient via API
    resp = client.post("/patients", json=patient_payload)
    if resp.status_code != 201:
        raise RuntimeError(f"Failed to create patient: {resp.status_code} {resp.text}")
    patient_id = resp.json()["id"]

    try:
        # 2) Test menu options response
        resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "menu"})
        if resp.status_code != 200:
            raise RuntimeError(f"Webhook failed: {resp.status_code} {resp.text}")
        content = resp.text
        if "3. Consulter mes rendez-vous" not in content or "4. Aide / Contacter la clinique" not in content:
            raise RuntimeError(f"Expected new menu options in response, got:\n{content}")

        # 3) Test querying status when no appointments exist
        resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "3"})
        if resp.status_code != 200:
            raise RuntimeError(f"Webhook failed: {resp.status_code} {resp.text}")
        content = resp.text
        if "aucun rendez-vous" not in content.lower():
            raise RuntimeError(f"Expected empty appointments message, got:\n{content}")

        # 4) Create a fake appointment (pending validation)
        # Create doc availability first
        availability = DisponibiliteMedecin(
            nom_medecin="Dr Smoke Test",
            specialite="Cardiologie",
            heure_debut=datetime.now(timezone.utc) + timedelta(days=2),
            heure_fin=datetime.now(timezone.utc) + timedelta(days=2, hours=1),
            est_disponible=False,
            est_bloque=True,
            motif_blocage="reservation_en_attente",
        )
        db.add(availability)
        db.commit()
        db.refresh(availability)

        appointment = RendezVous(
            patient_id=patient_id,
            disponibilite_id=availability.id,
            demandeur_prenom="Chatbot",
            demandeur_nom="Test",
            demandeur_age=36,
            numero_telephone_contact="+9999990033",
            nom_medecin="Dr Smoke Test",
            specialite="Cardiologie",
            heure_debut=availability.heure_debut,
            heure_fin=availability.heure_fin,
            motif="Demande WhatsApp en attente de validation",
            statut="en_attente",
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        # 5) Query status again, expect "En attente de validation"
        resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "3"})
        if resp.status_code != 200:
            raise RuntimeError(f"Webhook failed: {resp.status_code} {resp.text}")
        content = resp.text
        if "En attente de validation" not in content or "Dr Smoke Test" not in content:
            raise RuntimeError(f"Expected pending appointment message, got:\n{content}")

        # 6) Update appointment status to "confirme"
        appointment.statut = "confirme"
        db.commit()

        # 7) Query status again, expect "Confirmé"
        resp = client.post("/twilio/whatsapp", data={"From": whatsapp_number, "Body": "mes rdv"})
        if resp.status_code != 200:
            raise RuntimeError(f"Webhook failed: {resp.status_code} {resp.text}")
        content = resp.text
        if "Confirmé" not in content or "Dr Smoke Test" not in content:
            raise RuntimeError(f"Expected confirmed appointment message, got:\n{content}")

        print("Chatbot appointments smoke test OK")

    finally:
        db.close()
        # Clean up
        db_cleanup = SessionLocal()
        cleanup_test_data(db_cleanup, whatsapp_prefix="whatsapp:+999999")
        db_cleanup.close()


if __name__ == "__main__":
    main()
