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

    patient_payload = {
        "numero_whatsapp": "whatsapp:+9999990030",
        "prenom": "Retrieve",
        "nom": "Smoke",
        "date_naissance": "1990-03-20",
    }
    create_patient = client.post("/patients", json=patient_payload)
    if create_patient.status_code != 201:
        raise RuntimeError(f"Patient create failed: {create_patient.status_code} {create_patient.text}")
    patient_id = create_patient.json()["id"]

    try:
        files = {
            "upload": ("resultat.pdf", b"%PDF-1.4\nSECURE_RETRIEVE_SMOKE\n", "application/pdf")
        }
        data = {
            "patient_id": str(patient_id),
            "analysis_type": "bilan",
            "analysis_date": "2026-05-26",
        }
        upload = client.post("/results/upload", data=data, files=files)
        if upload.status_code != 200:
            raise RuntimeError(f"Result upload failed: {upload.status_code} {upload.text}")
        result_id = upload.json()["result_id"]

        otp = client.post(
            "/otp/request",
            json={"numero_whatsapp": patient_payload["numero_whatsapp"], "objectif": "result_access"},
        )
        if otp.status_code != 200:
            raise RuntimeError(f"OTP request failed: {otp.status_code} {otp.text}")
        otp_code = otp.json().get("otp_code")
        if not otp_code:
            raise RuntimeError("Missing otp_code in debug mode")

        secure = client.post(
            "/results/retrieve-secure",
            json={
                "result_id": result_id,
                "numero_whatsapp": patient_payload["numero_whatsapp"],
                "otp_code": otp_code,
                "objectif": "result_access",
            },
        )
        if secure.status_code != 200:
            raise RuntimeError(f"Secure retrieve failed: {secure.status_code} {secure.text}")
        if secure.headers.get("content-type", "").split(";")[0] != "application/pdf":
            raise RuntimeError(f"Unexpected content-type: {secure.headers.get('content-type')}")
        if b"SECURE_RETRIEVE_SMOKE" not in secure.content:
            raise RuntimeError("Decrypted payload content mismatch")

        # OTP should be consumed after successful retrieval.
        second_try = client.post(
            "/results/retrieve-secure",
            json={
                "result_id": result_id,
                "numero_whatsapp": patient_payload["numero_whatsapp"],
                "otp_code": otp_code,
                "objectif": "result_access",
            },
        )
        if second_try.status_code not in (404, 400, 429):
            raise RuntimeError(f"Unexpected OTP reuse status: {second_try.status_code} {second_try.text}")

        print("Secure retrieve smoke test OK: OTP + decrypt + file response")
    finally:
        client.get("/results")
        client.delete(f"/patients/{patient_id}")


if __name__ == "__main__":
    main()
