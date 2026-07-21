import os
import sys
import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.main import app
from app.db import SessionLocal
from app.models import Utilisateur, JournalMessage


def main() -> None:
    client = TestClient(app)

    db = SessionLocal()
    try:
        # Clean up any previous test_doc
        db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "test_doc_reminder").delete()
        db.query(JournalMessage).filter(JournalMessage.numero_destinataire == "dr.reminder@example.com").delete()
        db.commit()
    finally:
        db.close()

    # Login to get admin session
    resp_login = client.post("/admin/login", json={"nom_utilisateur": "admin", "mot_de_passe": "admin"})
    if resp_login.status_code != 200:
        raise RuntimeError(f"Login failed: {resp_login.status_code}")

    # 1. Create doctor user with telephone and email
    new_doc_payload = {
        "nom_utilisateur": "test_doc_reminder",
        "mot_de_passe": "password123",
        "role": "doctor",
        "numero_telephone": "+33612345678",
        "email": "dr.reminder@example.com"
    }

    create_resp = client.post("/admin/users", json=new_doc_payload)
    if create_resp.status_code != 201:
        raise RuntimeError(f"Failed to create doctor: {create_resp.status_code} {create_resp.text}")

    created_user = create_resp.json()
    assert created_user["nom_utilisateur"] == "test_doc_reminder"
    assert created_user["role"] == "doctor"
    assert created_user["numero_telephone"] == "+33612345678"
    assert created_user["email"] == "dr.reminder@example.com"

    # 2. List users and check fields are returned
    list_resp = client.get("/admin/users")
    if list_resp.status_code != 200:
        raise RuntimeError(f"Failed to list users: {list_resp.status_code}")
    users = list_resp.json()
    doc_user = next((u for u in users if u["nom_utilisateur"] == "test_doc_reminder"), None)
    if not doc_user:
        raise RuntimeError("Created doctor user not found in user listing")
    assert doc_user["numero_telephone"] == "+33612345678"
    assert doc_user["email"] == "dr.reminder@example.com"

    # Remove email log file if it exists to verify new file creation
    email_log_path = "email_simulation.log"
    if os.path.exists(email_log_path):
        os.remove(email_log_path)

    # 3. Trigger doctor slot reminders
    remind_resp = client.post("/admin/users/remind-slots")
    if remind_resp.status_code != 200:
        raise RuntimeError(f"Failed to trigger reminders: {remind_resp.status_code} {remind_resp.text}")
    
    result = remind_resp.json()
    print("Reminder trigger result:", result)
    assert "rappels envoyés" in result["message"]

    # 4. Check that email was logged in email_simulation.log and JournalMessage
    if not os.path.exists(email_log_path):
        raise RuntimeError("email_simulation.log file was not created")

    with open(email_log_path, "r", encoding="utf-8") as f:
        log_lines = f.readlines()
    
    found_email = False
    for line in log_lines:
        record = json.loads(line)
        if record["to"] == "dr.reminder@example.com":
            found_email = True
            assert "Rappel Docteur" in record["body"]
            break
    
    assert found_email, "Email log record was not found in simulation file"

    db = SessionLocal()
    try:
        db_log = db.query(JournalMessage).filter(JournalMessage.numero_destinataire == "dr.reminder@example.com").first()
        if not db_log:
            raise RuntimeError("JournalMessage was not saved for email reminder")
        assert db_log.via == "email"
        assert "Rappel Docteur" in db_log.corps

        # Clean up
        db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "test_doc_reminder").delete()
        db.query(JournalMessage).filter(JournalMessage.numero_destinataire == "dr.reminder@example.com").delete()
        db.commit()
    finally:
        db.close()

    print("Doctor slot reminders smoke test OK!")


if __name__ == "__main__":
    main()
