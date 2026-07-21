import os
import sys

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

    response = client.get("/admin")
    if response.status_code != 200:
        raise RuntimeError(f"Admin page failed: {response.status_code} {response.text}")

    html = response.text
    required_tokens = [
        "Tableau de bord clinique",
        "Créer un patient",
        "Créer un creneau médecin",
        "Uploader un resultat",
        "Réserver un rendez-vous",
        "loadPatients",
        "loadAppointments",
    ]
    for token in required_tokens:
        if token not in html:
            raise RuntimeError(f"Missing admin UI token: {token}")

    print("Admin smoke test OK: dashboard rendered")


if __name__ == "__main__":
    main()
