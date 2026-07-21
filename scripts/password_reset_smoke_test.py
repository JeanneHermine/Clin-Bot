import os
import sys
import json
import re
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
        # Clean up previous test users/messages
        db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "reset_smoke_doc").delete()
        db.query(JournalMessage).filter(JournalMessage.numero_destinataire == "reset_smoke@example.com").delete()
        db.commit()
    finally:
        db.close()

    # Login to get admin session
    resp_login = client.post("/admin/login", json={"nom_utilisateur": "admin", "mot_de_passe": "admin"})
    if resp_login.status_code != 200:
        raise RuntimeError(f"Login failed: {resp_login.status_code}")

    # 1. Create a doctor user with a valid email
    new_doc_payload = {
        "nom_utilisateur": "reset_smoke_doc",
        "mot_de_passe": "old_pass_123",
        "role": "doctor",
        "email": "reset_smoke@example.com"
    }
    create_resp = client.post("/admin/users", json=new_doc_payload)
    if create_resp.status_code != 201:
        raise RuntimeError(f"Failed to create doctor: {create_resp.status_code} {create_resp.text}")

    # 2. Try to create a user with invalid email format (should fail)
    invalid_doc_payload = {
        "nom_utilisateur": "reset_smoke_doc2",
        "mot_de_passe": "old_pass_123",
        "role": "doctor",
        "email": "invalid_email_format"
    }
    create_invalid_resp = client.post("/admin/users", json=invalid_doc_payload)
    if create_invalid_resp.status_code != 422:
        raise RuntimeError(f"Expected 422 for invalid email, got {create_invalid_resp.status_code} {create_invalid_resp.text}")
    print("Invalid email format check OK")

    # Clear log file
    email_log_path = "email_simulation.log"
    if os.path.exists(email_log_path):
        os.remove(email_log_path)

    # 3. Request a password reset
    forgot_resp = client.post("/admin/forgot-password", json={"nom_utilisateur": "reset_smoke_doc"})
    if forgot_resp.status_code != 200:
        raise RuntimeError(f"Forgot password request failed: {forgot_resp.status_code} {forgot_resp.text}")

    assert "un lien de réinitialisation a été envoyé" in forgot_resp.json()["message"]

    # 4. Read the token from email_simulation.log
    if not os.path.exists(email_log_path):
        raise RuntimeError("email_simulation.log file was not created for forgot password")

    with open(email_log_path, "r", encoding="utf-8") as f:
        log_lines = f.readlines()

    token = None
    for line in log_lines:
        record = json.loads(line)
        if record["to"] == "reset_smoke@example.com":
            body = record["body"]
            match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
            if match:
                token = match.group(1)
                break

    if not token:
        raise RuntimeError("Could not find reset token in email_simulation.log")

    print(f"Found reset token: {token}")

    # 5. Call GET /admin/reset-password page to check if it returns 200
    page_resp = client.get(f"/admin/reset-password?token={token}")
    if page_resp.status_code != 200:
        raise RuntimeError(f"GET /admin/reset-password failed: {page_resp.status_code}")
    assert "__RESET_TOKEN__" not in page_resp.text
    print("GET reset password page OK")

    # 6. Reset password via POST /admin/reset-password
    reset_payload = {
        "token": token,
        "mot_de_passe": "new_pass_secure_456"
    }
    reset_post_resp = client.post("/admin/reset-password", json=reset_payload)
    if reset_post_resp.status_code != 200:
        raise RuntimeError(f"POST /admin/reset-password failed: {reset_post_resp.status_code} {reset_post_resp.text}")
    assert "réinitialisé avec succès" in reset_post_resp.json()["message"]
    print("POST reset password OK")

    # 7. Verify the user can log in with new password
    login_resp = client.post("/admin/login", json={"nom_utilisateur": "reset_smoke_doc", "mot_de_passe": "new_pass_secure_456"})
    if login_resp.status_code != 200:
        raise RuntimeError(f"Login with new password failed: {login_resp.status_code} {login_resp.text}")
    print("Login with new password OK")

    # Clean up
    db = SessionLocal()
    try:
        db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "reset_smoke_doc").delete()
        db.query(JournalMessage).filter(JournalMessage.numero_destinataire == "reset_smoke@example.com").delete()
        db.commit()
    finally:
        db.close()

    print("Password reset smoke test OK!")


if __name__ == "__main__":
    main()
