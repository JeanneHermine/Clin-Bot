import os
import sys
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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

    patient_payload = {
        "numero_whatsapp": "whatsapp:+9999990040",
        "prenom": "Appointment",
        "nom": "Smoke",
        "date_naissance": "1988-08-08",
    }
    patient_resp = client.post("/patients", json=patient_payload)
    if patient_resp.status_code != 201:
        raise RuntimeError(f"Patient create failed: {patient_resp.status_code} {patient_resp.text}")
    patient_id = patient_resp.json()["id"]

    start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
    end_time = start_time + timedelta(minutes=30)

    availability_payload = {
        "nom_medecin": "Dr Smoke",
        "specialite": "Cardiologie",
        "heure_debut": start_time.isoformat(),
        "heure_fin": end_time.isoformat(),
        "est_bloque": False,
        "motif_blocage": None,
    }
    availability_resp = client.post("/availabilities", json=availability_payload)
    if availability_resp.status_code != 201:
        raise RuntimeError(f"Availability create failed: {availability_resp.status_code} {availability_resp.text}")
    availability_id = availability_resp.json()["id"]

    list_resp = client.get("/availabilities", params={"only_available": True})
    if list_resp.status_code != 200:
        raise RuntimeError(f"Availability list failed: {list_resp.status_code} {list_resp.text}")

    appt_payload = {
        "patient_id": patient_id,
        "disponibilite_id": availability_id,
        "nom_medecin": "Dr Smoke",
        "specialite": "Cardiologie",
        "heure_debut": start_time.isoformat(),
        "heure_fin": end_time.isoformat(),
        "motif": "consultation de controle",
    }
    appt_resp = client.post("/appointments", json=appt_payload)
    if appt_resp.status_code != 201:
        raise RuntimeError(f"Appointment create failed: {appt_resp.status_code} {appt_resp.text}")
    appointment_id = appt_resp.json()["id"]

    # availability should now be reserved / blocked
    availability_after = client.get(f"/availabilities/{availability_id}")
    if availability_after.status_code != 200:
        raise RuntimeError(f"Availability get failed: {availability_after.status_code} {availability_after.text}")
    slot = availability_after.json()
    if slot["est_disponible"] is not False or slot["est_bloque"] is not True:
        raise RuntimeError("Availability was not marked as reserved/blocked after appointment creation")

    # second reservation on same slot should fail
    second_resp = client.post("/appointments", json=appt_payload)
    if second_resp.status_code != 409:
        raise RuntimeError(f"Expected 409 for reused slot, got {second_resp.status_code} {second_resp.text}")

    # update appointment
    update_resp = client.patch(f"/appointments/{appointment_id}", json={"statut": "confirme", "motif": "suivi"})
    if update_resp.status_code != 200:
        raise RuntimeError(f"Appointment update failed: {update_resp.status_code} {update_resp.text}")

    updated = client.get(f"/appointments/{appointment_id}")
    if updated.status_code != 200 or updated.json()["statut"] != "confirme":
        raise RuntimeError(f"Appointment confirm check failed: {updated.status_code} {updated.text}")

    # list/get appointment
    list_appts = client.get("/appointments", params={"patient_id": patient_id})
    if list_appts.status_code != 200:
        raise RuntimeError(f"Appointment list failed: {list_appts.status_code} {list_appts.text}")

    get_appt = client.get(f"/appointments/{appointment_id}")
    if get_appt.status_code != 200:
        raise RuntimeError(f"Appointment get failed: {get_appt.status_code} {get_appt.text}")

    # delete appointment should free slot
    del_resp = client.delete(f"/appointments/{appointment_id}")
    if del_resp.status_code != 204:
        raise RuntimeError(f"Appointment delete failed: {del_resp.status_code} {del_resp.text}")

    availability_freed = client.get(f"/availabilities/{availability_id}")
    if availability_freed.status_code != 200:
        raise RuntimeError(f"Availability re-get failed: {availability_freed.status_code} {availability_freed.text}")
    slot2 = availability_freed.json()
    if slot2["est_disponible"] is not True or slot2["est_bloque"] is not False:
        raise RuntimeError("Availability was not released after appointment deletion")

    # cleanup
    client.delete(f"/availabilities/{availability_id}")
    client.delete(f"/patients/{patient_id}")

    print("Appointments smoke test OK: availabilities + reservations + release")


if __name__ == "__main__":
    main()
