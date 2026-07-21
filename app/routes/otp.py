from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import DefiOtp, Patient
from app.schemas import OtpRequestIn, OtpRequestOut, OtpVerifyIn, OtpVerifyOut
from app.services.otp_service import (
    build_expiry,
    consume_otp_or_raise,
    compute_otp_hash,
    generate_otp_code,
)
from app.services.message_gateway import get_message_gateway

# Délai minimum entre deux demandes OTP pour le même numéro+objectif (en secondes)
OTP_REQUEST_COOLDOWN_SECONDS = 60

router = APIRouter(prefix="/otp", tags=["otp"])


@router.post("/request", response_model=OtpRequestOut)
def request_otp(payload: OtpRequestIn, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.numero_whatsapp == payload.numero_whatsapp).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable pour ce numero WhatsApp.")

    # Rate-limiting : vérifier si un OTP récent (< cooldown) existe déjà
    cooldown_threshold = datetime.now(timezone.utc) - timedelta(seconds=OTP_REQUEST_COOLDOWN_SECONDS)
    recent = (
        db.query(DefiOtp)
        .filter(
            DefiOtp.numero_whatsapp == payload.numero_whatsapp,
            DefiOtp.objectif == payload.objectif,
            DefiOtp.est_consomme.is_(False),
            DefiOtp.cree_le >= cooldown_threshold,
        )
        .first()
    )
    if recent is not None:
        seconds_remaining = OTP_REQUEST_COOLDOWN_SECONDS
        if recent.cree_le:
            cree_le = recent.cree_le
            if cree_le.tzinfo is None:
                cree_le = cree_le.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - cree_le).total_seconds()
            seconds_remaining = max(0, int(OTP_REQUEST_COOLDOWN_SECONDS - elapsed))
        raise HTTPException(
            status_code=429,
            detail=f"Un OTP a deja ete envoye recemment. Veuillez patienter {seconds_remaining} secondes avant de redemander.",
        )

    # Invalider les anciens challenges actifs pour ce numéro + objectif
    active = (
        db.query(DefiOtp)
        .filter(
            DefiOtp.numero_whatsapp == payload.numero_whatsapp,
            DefiOtp.objectif == payload.objectif,
            DefiOtp.est_consomme.is_(False),
        )
        .all()
    )
    for challenge in active:
        challenge.est_consomme = True

    otp_code = generate_otp_code()
    challenge = DefiOtp(
        patient_id=patient.id,
        numero_whatsapp=payload.numero_whatsapp,
        objectif=payload.objectif,
        hash_code=compute_otp_hash(
            secret_key=settings.secret_key,
            whatsapp_number=payload.numero_whatsapp,
            purpose=payload.objectif,
            code=otp_code,
        ),
        expire_le=build_expiry(settings.otp_expiry_minutes),
        tentatives=0,
        tentatives_max=settings.otp_max_attempts,
        est_consomme=False,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    # Envoyer l'OTP par SMS (Double Facteur) via le gateway configuré
    gateway = get_message_gateway()
    message_body = f"Votre code OTP pour {payload.objectif} est: {otp_code}. Valide {settings.otp_expiry_minutes} minutes."
    try:
        gateway.send_sms(payload.numero_whatsapp, message_body)
    except Exception:
        # Ne pas faire échouer la requête si l'envoi échoue (Twilio désactivé ou réseau)
        pass

    return OtpRequestOut(
        challenge_id=challenge.id,
        numero_whatsapp=challenge.numero_whatsapp,
        objectif=challenge.objectif,
        expire_le=challenge.expire_le,
        tentatives_max=challenge.tentatives_max,
        otp_code=otp_code if settings.otp_debug_return_code else None,
    )


@router.post("/verify", response_model=OtpVerifyOut)
def verify_otp(payload: OtpVerifyIn, db: Session = Depends(get_db)):
    consume_otp_or_raise(
        db,
        secret_key=settings.secret_key,
        whatsapp_number=payload.numero_whatsapp,
        purpose=payload.objectif,
        code=payload.code,
    )

    return OtpVerifyOut(verified=True, message="OTP valide.")
