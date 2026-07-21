import os
import sys
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

from app.main import app
from app.db import SessionLocal
from app.models import Patient, Utilisateur
from app.services.auth_service import hash_password

def main() -> None:
    # 1. Create a clean test database session
    db = SessionLocal()
    try:
        # Create default admin if not exists
        admin = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "admin").first()
        if not admin:
            admin = Utilisateur(nom_utilisateur="admin", mot_de_passe_hashe=hash_password("admin"), role="admin")
            db.add(admin)
            db.commit()

        # Add mock patients for testing search
        p1 = Patient(prenom="Jean", nom="Dupont", numero_whatsapp="whatsapp:+33600000001", date_naissance="1990-01-01")
        p2 = Patient(prenom="Marie", nom="Durand", numero_whatsapp="whatsapp:+33600000002", date_naissance="1992-05-10")
        p3 = Patient(prenom="Jean-Marc", nom="Petit", numero_whatsapp="whatsapp:+33600000003", date_naissance="1985-08-20")
        
        # Clean existing test data first
        db.query(Patient).filter(Patient.numero_whatsapp.in_([p1.numero_whatsapp, p2.numero_whatsapp, p3.numero_whatsapp])).delete()
        db.commit()

        db.add(p1)
        db.add(p2)
        db.add(p3)
        db.commit()

        p1_id, p2_id, p3_id = p1.id, p2.id, p3.id
    finally:
        db.close()

    client = TestClient(app)

    # Login to get session
    resp_login = client.post("/admin/login", json={"nom_utilisateur": "admin", "mot_de_passe": "admin"})
    if resp_login.status_code != 200:
        raise RuntimeError(f"Login failed: {resp_login.status_code}")

    # Test 1: Search with no query should return empty list
    resp = client.get("/patients/search?q=")
    assert resp.status_code == 200
    assert resp.json() == []

    # Test 2: Search for "Jean" should return p1 ("Jean Dupont") and p3 ("Jean-Marc Petit")
    resp = client.get("/patients/search?q=Jean")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 2
    ids = [r["id"] for r in results]
    assert p1_id in ids
    assert p3_id in ids

    # Test 3: Search for "durand" (case insensitivity) should return p2 ("Marie Durand")
    resp = client.get("/patients/search?q=durand")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    ids = [r["id"] for r in results]
    assert p2_id in ids

    # Test 4: Search for concatenated name "Jean Dupont"
    resp = client.get("/patients/search?q=Jean%20Dupont")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    ids = [r["id"] for r in results]
    assert p1_id in ids

    # Test 5: Search for concatenated name reverse "Dupont Jean"
    resp = client.get("/patients/search?q=Dupont%20Jean")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    ids = [r["id"] for r in results]
    assert p1_id in ids

    # Cleanup test patients
    db = SessionLocal()
    try:
        db.query(Patient).filter(Patient.id.in_([p1_id, p2_id, p3_id])).delete()
        db.commit()
    finally:
        db.close()

    print("Patient search API smoke test OK!")

if __name__ == "__main__":
    main()
