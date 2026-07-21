import os
import sys
from datetime import date
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Ensure a valid key is available before importing app settings.
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

from app.db import SessionLocal
from app.main import app
from app.models import Patient, Resultat


def main() -> None:
    db = SessionLocal()
    client = TestClient(app)
    created_patient_id = None
    created_result_id = None
    created_file_path = None

    try:
        # Login to get session
        from app.models import Utilisateur
        from app.services.auth_service import hash_password
        admin = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "admin").first()
        if not admin:
            admin = Utilisateur(nom_utilisateur="admin", mot_de_passe_hashe=hash_password("admin"), role="admin")
            db.add(admin)
            db.commit()

        resp_login = client.post("/admin/login", json={"nom_utilisateur": "admin", "mot_de_passe": "admin"})
        if resp_login.status_code != 200:
            raise RuntimeError(f"Login failed: {resp_login.status_code}")

        patient = Patient(
            numero_whatsapp="whatsapp:+9999990002",
            prenom="Upload",
            nom="Smoke",
            date_naissance=date(1999, 12, 31),
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        created_patient_id = patient.id

        files = {
            "upload": ("resultat.pdf", b"%PDF-1.4\n%SMOKE_TEST\n", "application/pdf")
        }
        data = {
            "patient_id": str(created_patient_id),
            "analysis_type": "prise_de_sang",
            "analysis_date": "2026-05-26",
        }
        response = client.post("/results/upload", data=data, files=files)

        if response.status_code != 200:
            raise RuntimeError(f"Upload failed: {response.status_code} {response.text}")

        payload = response.json()
        created_result_id = payload["result_id"]
        created_file_path = payload["stored_file_path"]

        if not payload.get("encrypted"):
            raise RuntimeError("Upload response should indicate encrypted storage.")

        if not Path(created_file_path).exists():
            raise RuntimeError("Encrypted file not found on disk.")

        print("Upload smoke test OK: validation + encryption + DB record")
    finally:
        if created_result_id is not None:
            db.query(Resultat).filter(Resultat.id == created_result_id).delete()
            db.commit()
        if created_patient_id is not None:
            db.query(Patient).filter(Patient.id == created_patient_id).delete()
            db.commit()
        if created_file_path and Path(created_file_path).exists():
            Path(created_file_path).unlink()
        db.close()


if __name__ == "__main__":
    main()
