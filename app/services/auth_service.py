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
            nom_utilisateur="admin",
            mot_de_passe_hashe=hash_password("admin"),
            role="admin"
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print("[AUTH] Default admin user created ('admin' / 'admin')", flush=True)


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
