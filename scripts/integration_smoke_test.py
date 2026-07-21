import os
import sys
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["OTP_DEBUG_RETURN_CODE"] = "true"

from app.db import SessionLocal
from app.main import app
from scripts.test_support import cleanup_test_data, purge_storage_dir


def main() -> None:
    client = TestClient(app)
    db = SessionLocal()

    created_ids = {
        "patient_ids": [],
        "result_ids": [],
        "availability_ids": [],
        "appointment_ids": [],
    }

    patient_number = "whatsapp:+9999990050"
    doctor_name = "Dr Smoke Integr"
    start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    end_time = start_time + timedelta(minutes=30)

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

        # Patient CRUD
        patient_resp = client.post(
            "/patients",
            json={
                "numero_whatsapp": patient_number,
                "prenom": "Integration",
                "nom": "Smoke",
                "date_naissance": "1991-04-04",
            },
        )
        if patient_resp.status_code != 201:
            raise RuntimeError(f"Patient create failed: {patient_resp.status_code} {patient_resp.text}")
        patient_id = patient_resp.json()["id"]
        created_ids["patient_ids"].append(patient_id)

        if client.get(f"/patients/{patient_id}").status_code != 200:
            raise RuntimeError("Patient get failed")

        # Availability CRUD + booking
        availability_resp = client.post(
            "/availabilities",
            json={
                "nom_medecin": doctor_name,
                "specialite": "Cardiologie",
                "heure_debut": start_time.isoformat(),
                "heure_fin": end_time.isoformat(),
                "est_bloque": False,
                "motif_blocage": None,
            },
        )
        if availability_resp.status_code != 201:
            raise RuntimeError(f"Availability create failed: {availability_resp.status_code} {availability_resp.text}")
        availability_id = availability_resp.json()["id"]
        created_ids["availability_ids"].append(availability_id)

        appointment_resp = client.post(
            "/appointments",
            json={
                "patient_id": patient_id,
                "disponibilite_id": availability_id,
                "nom_medecin": doctor_name,
                "specialite": "Cardiologie",
                "heure_debut": start_time.isoformat(),
                "heure_fin": end_time.isoformat(),
                "motif": "integ test",
            },
        )
        if appointment_resp.status_code != 201:
            raise RuntimeError(f"Appointment create failed: {appointment_resp.status_code} {appointment_resp.text}")
        appointment_id = appointment_resp.json()["id"]
        created_ids["appointment_ids"].append(appointment_id)

        # Result upload + OTP + secure retrieval
        upload_resp = client.post(
            "/results/upload",
            data={
                "patient_id": str(patient_id),
                "analysis_type": "bilan",
                "analysis_date": "2026-05-26",
            },
            files={"upload": ("result.pdf", b"%PDF-1.4\nINTEGRATION_SMOKE\n", "application/pdf")},
        )
        if upload_resp.status_code != 200:
            raise RuntimeError(f"Result upload failed: {upload_resp.status_code} {upload_resp.text}")
        result_id = upload_resp.json()["result_id"]
        created_ids["result_ids"].append(result_id)

        otp_resp = client.post(
            "/otp/request",
            json={"numero_whatsapp": patient_number, "objectif": "result_access"},
        )
        if otp_resp.status_code != 200:
            raise RuntimeError(f"OTP request failed: {otp_resp.status_code} {otp_resp.text}")
        otp_code = otp_resp.json().get("otp_code")
        if not otp_code:
            raise RuntimeError("OTP code missing in debug mode")

        secure_resp = client.post(
            "/results/retrieve-secure",
            json={
                "result_id": result_id,
                "numero_whatsapp": patient_number,
                "otp_code": otp_code,
                "objectif": "result_access",
            },
        )
        if secure_resp.status_code != 200:
            raise RuntimeError(f"Secure retrieve failed: {secure_resp.status_code} {secure_resp.text}")
        if b"INTEGRATION_SMOKE" not in secure_resp.content:
            raise RuntimeError("Secure retrieve payload mismatch")

        # CRUD list checks
        if client.get("/patients").status_code != 200:
            raise RuntimeError("Patient list failed")
        if client.get("/results", params={"patient_id": patient_id}).status_code != 200:
            raise RuntimeError("Result list failed")
        if client.get("/availabilities", params={"only_available": False}).status_code != 200:
            raise RuntimeError("Availability list failed")
        if client.get("/appointments", params={"patient_id": patient_id}).status_code != 200:
            raise RuntimeError("Appointment list failed")

        # Admin page render sanity check
        admin_resp = client.get("/admin")
        if admin_resp.status_code != 200 or "Tableau de bord clinique" not in admin_resp.text:
            raise RuntimeError("Admin dashboard failed to render")

        print("Integration smoke test OK: patients + results + otp + appointments + admin")
    finally:
        cleanup_test_data(
            db,
            patient_ids=created_ids["patient_ids"],
            result_ids=created_ids["result_ids"],
            availability_ids=created_ids["availability_ids"],
            appointment_ids=created_ids["appointment_ids"],
        )
        purge_storage_dir()
        db.close()


if __name__ == "__main__":
    main()
