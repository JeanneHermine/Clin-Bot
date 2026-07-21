import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Ensure a valid key is available before importing app settings.
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

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

    # 1) Create patient
    patient_payload = {
        "numero_whatsapp": "whatsapp:+9999990010",
        "prenom": "Crud",
        "nom": "Smoke",
        "date_naissance": "1995-01-15",
        "numero_telephone_secondaire": "whatsapp:+9999990020",
    }
    resp = client.post("/patients", json=patient_payload)
    if resp.status_code != 201:
        raise RuntimeError(f"Patient create failed: {resp.status_code} {resp.text}")
    created_patient = resp.json()
    patient_id = created_patient["id"]
    if created_patient.get("numero_telephone_secondaire") != "whatsapp:+9999990020":
        raise RuntimeError(f"Expected numero_telephone_secondaire in response, got: {created_patient}")

    # 2) List/get/update patient
    resp = client.get("/patients")
    if resp.status_code != 200:
        raise RuntimeError(f"Patient list failed: {resp.status_code} {resp.text}")

    resp = client.get(f"/patients/{patient_id}")
    if resp.status_code != 200:
        raise RuntimeError(f"Patient get failed: {resp.status_code} {resp.text}")
    if resp.json().get("numero_telephone_secondaire") != "whatsapp:+9999990020":
        raise RuntimeError("Patient get missing numero_telephone_secondaire")

    resp = client.patch(
        f"/patients/{patient_id}",
        json={"prenom": "CrudUpdated", "numero_telephone_secondaire": "whatsapp:+9999990030"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Patient update failed: {resp.status_code} {resp.text}")
    if resp.json().get("numero_telephone_secondaire") != "whatsapp:+9999990030":
        raise RuntimeError("Patient update failed to update numero_telephone_secondaire")

    # 3) Upload result then list/get/update/delete result
    files = {
        "upload": ("resultat.pdf", b"%PDF-1.4\n%CRUD_SMOKE\n", "application/pdf")
    }
    data = {
        "patient_id": str(patient_id),
        "analysis_type": "radio",
        "analysis_date": "2026-05-26",
    }
    resp = client.post("/results/upload", data=data, files=files)
    if resp.status_code != 200:
        raise RuntimeError(f"Result upload failed: {resp.status_code} {resp.text}")

    upload_payload = resp.json()
    result_id = upload_payload["result_id"]
    encrypted_path = upload_payload["stored_file_path"]

    resp = client.get("/results")
    if resp.status_code != 200:
        raise RuntimeError(f"Result list failed: {resp.status_code} {resp.text}")

    resp = client.get(f"/results/{result_id}")
    if resp.status_code != 200:
        raise RuntimeError(f"Result get failed: {resp.status_code} {resp.text}")

    resp = client.patch(f"/results/{result_id}", json={"statut": "envoye"})
    if resp.status_code != 200:
        raise RuntimeError(f"Result update failed: {resp.status_code} {resp.text}")

    resp = client.delete(f"/results/{result_id}")
    if resp.status_code != 204:
        raise RuntimeError(f"Result delete failed: {resp.status_code} {resp.text}")

    if Path(encrypted_path).exists():
        raise RuntimeError("Encrypted file should be removed on result deletion")

    # 4) Delete patient
    resp = client.delete(f"/patients/{patient_id}")
    if resp.status_code != 204:
        raise RuntimeError(f"Patient delete failed: {resp.status_code} {resp.text}")

    print("CRUD API smoke test OK: patients + results")


if __name__ == "__main__":
    main()
