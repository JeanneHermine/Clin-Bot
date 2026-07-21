import os
import sys

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Ensure deterministic local dev behavior for the smoke test.
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
        "numero_whatsapp": "whatsapp:+9999990020",
        "prenom": "Otp",
        "nom": "Smoke",
        "date_naissance": "1992-07-10",
    }
    resp = client.post("/patients", json=patient_payload)
    if resp.status_code == 201:
        patient_id = resp.json()["id"]
    elif resp.status_code == 409:
        # Reuse existing patient if already present from previous run.
        existing = client.get("/patients")
        patient_id = next(
            p["id"] for p in existing.json() if p["numero_whatsapp"] == patient_payload["numero_whatsapp"]
        )
    else:
        raise RuntimeError(f"Patient setup failed: {resp.status_code} {resp.text}")

    # Request OTP and keep preview code (dev mode).
    req = client.post(
        "/otp/request",
        json={"numero_whatsapp": patient_payload["numero_whatsapp"], "objectif": "result_access"},
    )
    if req.status_code != 200:
        raise RuntimeError(f"OTP request failed: {req.status_code} {req.text}")
    otp_code = req.json().get("otp_code")
    if not otp_code:
        raise RuntimeError("OTP debug code is missing in request response")

    # Fail 3 times to trigger anti brute-force lock.
    for _ in range(2):
        bad = client.post(
            "/otp/verify",
            json={
                "numero_whatsapp": patient_payload["numero_whatsapp"],
                "objectif": "result_access",
                "code": "000000",
            },
        )
        if bad.status_code != 400:
            raise RuntimeError(f"Expected 400 for invalid OTP, got {bad.status_code} {bad.text}")

    third = client.post(
        "/otp/verify",
        json={
            "numero_whatsapp": patient_payload["numero_whatsapp"],
            "objectif": "result_access",
            "code": "000000",
        },
    )
    if third.status_code != 429:
        raise RuntimeError(f"Expected 429 on third wrong OTP, got {third.status_code} {third.text}")

    # Request new OTP then verify correctly.
    req2 = client.post(
        "/otp/request",
        json={"numero_whatsapp": patient_payload["numero_whatsapp"], "objectif": "result_access"},
    )
    if req2.status_code != 200:
        raise RuntimeError(f"Second OTP request failed: {req2.status_code} {req2.text}")
    otp_code_2 = req2.json().get("otp_code")
    if not otp_code_2:
        raise RuntimeError("Second OTP debug code missing")

    ok = client.post(
        "/otp/verify",
        json={
            "numero_whatsapp": patient_payload["numero_whatsapp"],
            "objectif": "result_access",
            "code": otp_code_2,
        },
    )
    if ok.status_code != 200:
        raise RuntimeError(f"Expected successful verification, got {ok.status_code} {ok.text}")

    # Optional cleanup of patient at the end.
    client.delete(f"/patients/{patient_id}")

    print("OTP smoke test OK: request + anti brute-force + verify")


if __name__ == "__main__":
    main()
