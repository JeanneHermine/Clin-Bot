import os
import sys

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["OTP_DEBUG_RETURN_CODE"] = "true"

from app.main import app


def main() -> None:
    client = TestClient(app)

    # Login to get session
    from app.db import SessionLocal
    from app.models import Utilisateur
    from app.services.auth_service import hash_password
    db = SessionLocal()
    try:
        admin = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "admin").first()
        if not admin:
            admin = Utilisateur(nom_utilisateur="admin", mot_de_passe_hashe=hash_password("admin"), role="admin")
            db.add(admin)
            db.commit()
    finally:
        db.close()

    resp_login = client.post("/admin/login", json={"nom_utilisateur": "admin", "mot_de_passe": "admin"})
    if resp_login.status_code != 200:
        raise RuntimeError(f"Login failed: {resp_login.status_code}")

    # 1. Create a dummy patient
    patient_payload = {
        "numero_whatsapp": "whatsapp:+9999990099",
        "prenom": "Manual",
        "nom": "Smoke",
        "date_naissance": "1995-05-15",
    }
    create_patient = client.post("/patients", json=patient_payload)
    if create_patient.status_code != 201:
        raise RuntimeError(f"Patient create failed: {create_patient.status_code} {create_patient.text}")
    patient_id = create_patient.json()["id"]

    try:
        # 2. Call /results/create-manual endpoint
        manual_payload = {
            "patient_id": patient_id,
            "type_analyse": "Bilan Sanguin Clinique",
            "date_analyse": "2026-06-17",
            "template_type": "blood",
            "results_data": {
                "glycemie": "0.98",
                "cholesterol": "1.92",
                "triglycerides": "1.30",
                "uree": "0.42",
                "creatinine": "9.1",
            }
        }
        manual_resp = client.post("/results/create-manual", json=manual_payload)
        if manual_resp.status_code != 200:
            raise RuntimeError(f"Manual result creation failed: {manual_resp.status_code} {manual_resp.text}")
        
        result_id = manual_resp.json()["result_id"]
        stored_file_path = manual_resp.json()["stored_file_path"]
        print(f"Manual result created with ID: {result_id}, stored at: {stored_file_path}")

        # 3. Download the decrypted result using the new download endpoint
        download_resp = client.get(f"/results/{result_id}/download")
        if download_resp.status_code != 200:
            raise RuntimeError(f"Admin download failed: {download_resp.status_code} {download_resp.text}")
        
        # Verify PDF header
        if not download_resp.content.startswith(b"%PDF-"):
            raise RuntimeError("Downloaded file is not a valid PDF")
        
        print("Downloaded file size:", len(download_resp.content), "bytes")
        print("Manual result smoke test OK: generation + encryption + admin download PDF")

    finally:
        # Cleanup
        client.delete(f"/patients/{patient_id}")
        print("Cleanup completed.")


if __name__ == "__main__":
    main()
