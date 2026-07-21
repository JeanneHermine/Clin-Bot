import os
import sys

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Force actual session authentication checking (no dev mode fallback)
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["OTP_DEBUG_RETURN_CODE"] = "false"

from app.config import settings
settings.otp_debug_return_code = False

from app.main import app


def main() -> None:
    client = TestClient(app)

    # Make sure default admin user exists
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

    # 1) Accessing dashboard without session should redirect to login page
    resp_dashboard = client.get("/admin", follow_redirects=False)
    if resp_dashboard.status_code != 307 or not resp_dashboard.headers.get("location", "").endswith("/admin/login"):
        raise RuntimeError(f"Expected redirect to /admin/login, got {resp_dashboard.status_code} {resp_dashboard.headers}")

    # 2) Accessing login page should return 200 HTML
    resp_login_page = client.get("/admin/login")
    if resp_login_page.status_code != 200:
        raise RuntimeError(f"Login page failed: {resp_login_page.status_code}")
    if "Connexion" not in resp_login_page.text:
        raise RuntimeError("Missing expected content in login page")

    # 3) Attempt login with invalid credentials
    invalid_login_payload = {
        "nom_utilisateur": "admin",
        "mot_de_passe": "wrong_password_123"
    }
    resp_bad_login = client.post("/admin/login", json=invalid_login_payload)
    if resp_bad_login.status_code != 400:
        raise RuntimeError(f"Expected 400 Bad Request, got: {resp_bad_login.status_code} {resp_bad_login.text}")

    # 4) Attempt login with valid credentials (default admin user)
    valid_login_payload = {
        "nom_utilisateur": "admin",
        "mot_de_passe": "admin"
    }
    resp_good_login = client.post("/admin/login", json=valid_login_payload)
    if resp_good_login.status_code != 200:
        raise RuntimeError(f"Expected 200 OK, got: {resp_good_login.status_code} {resp_good_login.text}")
    
    login_data = resp_good_login.json()
    if login_data.get("role") != "admin" or login_data.get("username") != "admin":
        raise RuntimeError(f"Unexpected login response data: {login_data}")

    # Verify session cookie is set
    session_cookie = client.cookies.get("cid_session")
    if not session_cookie:
        raise RuntimeError("Session cookie 'cid_session' was not set on successful login")

    # 5) Access dashboard with authenticated session
    resp_dashboard_auth = client.get("/admin")
    if resp_dashboard_auth.status_code != 200:
        raise RuntimeError(f"Accessing dashboard with active session failed: {resp_dashboard_auth.status_code}")
    if "@admin" not in resp_dashboard_auth.text or "logout-btn" not in resp_dashboard_auth.text:
        raise RuntimeError("Authenticated dashboard text verification failed")

    # 6) Access users list with authenticated session
    resp_users = client.get("/admin/users")
    if resp_users.status_code != 200:
        raise RuntimeError(f"Accessing users list failed: {resp_users.status_code}")

    # 7) Logout and verify session cookie is cleared
    resp_logout = client.post("/admin/logout")
    if resp_logout.status_code != 200:
        raise RuntimeError(f"Logout endpoint failed: {resp_logout.status_code}")
    
    # Check session cookie is gone or empty
    session_cookie_after = client.cookies.get("cid_session")
    if session_cookie_after and session_cookie_after != "":
        raise RuntimeError("Session cookie was not cleared after logout")

    # 8) Re-accessing dashboard after logout should redirect again
    resp_dashboard_logged_out = client.get("/admin", follow_redirects=False)
    if resp_dashboard_logged_out.status_code != 307:
        raise RuntimeError(f"Expected redirect after logout, got: {resp_dashboard_logged_out.status_code}")

    print("Admin authentication smoke test OK: login + redirect + session cookie + logout")


if __name__ == "__main__":
    main()
