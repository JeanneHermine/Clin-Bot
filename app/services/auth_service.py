import hashlib
import hmac
import secrets
from sqlalchemy.orm import Session
from app.models import Utilisateur


def hash_password(password: str) -> str:
    """Hash password using PBKDF2 with a random salt."""
    salt = secrets.token_hex(16)
    iterations = 100_000
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    )
    return f"{salt}:{iterations}:{hashed.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its PBKDF2 hash."""
    try:
        salt, iterations_str, hashed_hex = hashed_password.split(":", 2)
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    )
    return hmac.compare_digest(candidate.hex(), hashed_hex)


def sign_session(username: str, secret_key: str) -> str:
    """Sign a username to generate a secure session string."""
    signature = hmac.new(
        secret_key.encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{username}:{signature}"


def verify_session(session_cookie: str, secret_key: str) -> str | None:
    """Verify a session signature and return the username if valid."""
    if not session_cookie:
        return None
    try:
        username, signature = session_cookie.split(":", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if hmac.compare_digest(signature, expected_signature):
        return username
    return None


def create_default_admin(db: Session) -> None:
    """Ensure at least one admin user exists in the database."""
    # Check if any user exists
    count = db.query(Utilisateur).count()
    if count == 0:
        admin_user = Utilisateur(
            nom_utilisateur="Roméo",
            mot_de_passe_hashe=hash_password("roméo123"),
            role="admin"
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print("[AUTH] Default admin user created ('Roméo' / 'roméo123')", flush=True)


from fastapi import Depends, HTTPException, Request
from app.db import get_db
from app.config import settings
from app.models import JournalAudit


def get_session_user(request: Request, db: Session = Depends(get_db)) -> Utilisateur | None:
    session_cookie = request.cookies.get("cid_session")
    if not session_cookie:
        return None
    username = verify_session(session_cookie, settings.secret_key)
    if not username:
        return None
    return db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == username).first()


def require_user(request: Request, db: Session = Depends(get_db)) -> Utilisateur:
    user = get_session_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Non authentifié.")
    return user


def log_activity(db: Session, username: str, action: str, details: str = None) -> JournalAudit:
    log = JournalAudit(nom_utilisateur=username, action=action, details=details)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def build_appointment_token(whatsapp_number: str, appointment_id: int, expires_at) -> str:
    import json
    import base64
    import hmac
    import hashlib
    from datetime import timezone
    from app.config import settings

    payload = {
        "whatsapp_number": whatsapp_number,
        "appointment_id": appointment_id,
        "expires_at": expires_at.astimezone(timezone.utc).isoformat(),
    }
    raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(raw_payload).decode("ascii").rstrip("=")
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_appointment_token(token: str) -> dict:
    import json
    import base64
    import hmac
    import hashlib
    from datetime import timezone
    from app.config import settings

    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Jeton de téléchargement invalide.") from exc

    expected_signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=403, detail="Jeton de téléchargement invalide.")

    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Jeton de téléchargement invalide.") from exc

    return payload
