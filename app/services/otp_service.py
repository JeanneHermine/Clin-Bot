import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import DefiOtp


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def compute_otp_hash(secret_key: str, whatsapp_number: str, purpose: str, code: str) -> str:
    payload = f"{whatsapp_number}:{purpose}:{code}".encode("utf-8")
    key = secret_key.encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def verify_otp_hash(
    secret_key: str,
    whatsapp_number: str,
    purpose: str,
    code: str,
    expected_hash: str,
) -> bool:
    candidate = compute_otp_hash(secret_key, whatsapp_number, purpose, code)
    return hmac.compare_digest(candidate, expected_hash)


def build_expiry(minutes: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def consume_otp_or_raise(
    db: Session,
    *,
    secret_key: str,
    whatsapp_number: str,
    purpose: str,
    code: str,
) -> DefiOtp:
    challenge = (
        db.query(DefiOtp)
        .filter(
            DefiOtp.numero_whatsapp == whatsapp_number,
            DefiOtp.objectif == purpose,
            DefiOtp.est_consomme.is_(False),
        )
        .order_by(DefiOtp.id.desc())
        .first()
    )
    if challenge is None:
        raise HTTPException(status_code=404, detail="Aucun OTP actif trouve.")

    now = datetime.now(timezone.utc)
    expires_at = challenge.expire_le
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        challenge.est_consomme = True
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expire. Demandez un nouveau code.")

    if challenge.tentatives >= challenge.tentatives_max:
        raise HTTPException(status_code=429, detail="OTP bloque apres trop de tentatives.")

    is_valid = verify_otp_hash(
        secret_key=secret_key,
        whatsapp_number=whatsapp_number,
        purpose=purpose,
        code=code,
        expected_hash=challenge.hash_code,
    )

    if not is_valid:
        challenge.tentatives += 1
        if challenge.tentatives >= challenge.tentatives_max:
            challenge.est_consomme = True
            db.commit()
            raise HTTPException(status_code=429, detail="OTP bloque apres trop de tentatives.")
        db.commit()
        remaining = challenge.tentatives_max - challenge.tentatives
        raise HTTPException(status_code=400, detail=f"Code OTP invalide. Tentatives restantes: {remaining}.")

    challenge.est_consomme = True
    challenge.verifie_le = now
    db.commit()
    db.refresh(challenge)
    return challenge
