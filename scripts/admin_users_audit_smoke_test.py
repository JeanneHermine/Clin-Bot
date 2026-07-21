import os
import sys

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Enable testing mode fallback to mock admin
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

    # 1) Get HTML dashboard and verify tab navigation presence
    resp_dashboard = client.get("/admin")
    if resp_dashboard.status_code != 200:
        raise RuntimeError(f"Dashboard render failed: {resp_dashboard.status_code}")
    
    html = resp_dashboard.text
    required_elements = [
        "tab-dashboard-btn",
        "tab-audit-btn",
        "tab-audit",
        "user-form",
        "users-table",
        "logs-table",
        "switchTab",
        "loadUsers",
        "loadAuditLogs",
        "deleteUser"
    ]
    for el in required_elements:
        if el not in html:
            raise RuntimeError(f"Dashboard missing expected element or script token: {el}")

    # 2) List existing users (there should at least be the default admin user)
    resp_list = client.get("/admin/users")
    if resp_list.status_code != 200:
        raise RuntimeError(f"List users failed: {resp_list.status_code} {resp_list.text}")
    users = resp_list.json()
    if not any(u["nom_utilisateur"] == "admin" for u in users):
        raise RuntimeError("Default admin user not found in user list")
    
    admin_id = next(u["id"] for u in users if u["nom_utilisateur"] == "admin")
 
    # 3) Create a new user
    new_user_payload = {
        "nom_utilisateur": "test_doc_smoke",
        "mot_de_passe": "secure_smoke_password",
        "role": "doctor"
    }
    resp_create = client.post("/admin/users", json=new_user_payload)
    if resp_create.status_code != 201:
        raise RuntimeError(f"Create user failed: {resp_create.status_code} {resp_create.text}")
    
    new_user = resp_create.json()
    new_user_id = new_user["id"]
    if new_user["nom_utilisateur"] != "test_doc_smoke" or new_user["role"] != "doctor":
        raise RuntimeError(f"Created user fields mismatch: {new_user}")

    # 4) Try to create a duplicate user (should fail)
    resp_dup = client.post("/admin/users", json=new_user_payload)
    if resp_dup.status_code != 400:
        raise RuntimeError(f"Duplicate user creation did not return 400: {resp_dup.status_code}")

    # 5) Try to delete yourself (admin deletes admin - should fail)
    resp_del_self = client.delete(f"/admin/users/{admin_id}")
    if resp_del_self.status_code != 400:
        raise RuntimeError(f"Deleting self did not return 400: {resp_del_self.status_code} {resp_del_self.text}")

    # 6) Delete the created user
    resp_delete = client.delete(f"/admin/users/{new_user_id}")
    if resp_delete.status_code != 204:
        raise RuntimeError(f"Delete user failed: {resp_delete.status_code} {resp_delete.text}")

    # 7) Retrieve audit logs and check for expected actions
    resp_logs = client.get("/admin/logs")
    if resp_logs.status_code != 200:
        raise RuntimeError(f"Get audit logs failed: {resp_logs.status_code} {resp_logs.text}")
    
    logs = resp_logs.json()
    create_log_found = any("Création de l'utilisateur @test_doc_smoke" in l["action"] for l in logs)
    delete_log_found = any("Suppression de l'utilisateur @test_doc_smoke" in l["action"] for l in logs)
    
    if not create_log_found:
        raise RuntimeError("Audit log for user creation not found")
    if not delete_log_found:
        raise RuntimeError("Audit log for user deletion not found")

    print("Admin users and audit logs smoke test OK: API endpoints + HTML integration")


if __name__ == "__main__":
    main()
