from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Patient, Utilisateur
from app.schemas import PatientCreate, PatientOut, PatientUpdate
from app.services.auth_service import require_user, log_activity


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    # Check if a patient with the same whatsapp number already exists
    existing_patient = db.query(Patient).filter(Patient.numero_whatsapp == payload.numero_whatsapp).first()
    if existing_patient is not None:
        existing_patient.prenom = payload.prenom
        existing_patient.nom = payload.nom
        existing_patient.date_naissance = payload.date_naissance
        existing_patient.numero_telephone_secondaire = payload.numero_telephone_secondaire
        db.commit()
        db.refresh(existing_patient)
        
        log_activity(db, current_user.nom_utilisateur, f"Mise à jour du patient #{existing_patient.id} lors de la création ({(existing_patient.nom or '').upper()} {existing_patient.prenom or ''})")
        return existing_patient

    patient = Patient(**payload.model_dump())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Numero WhatsApp deja utilise.") from exc
    db.refresh(patient)
    
    log_activity(db, current_user.nom_utilisateur, f"Création du patient #{patient.id} ({(patient.nom or '').upper()} {patient.prenom or ''})")
    
    return patient


@router.get("", response_model=list[PatientOut])
def list_patients(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    return db.query(Patient).order_by(Patient.id.asc()).all()


@router.get("/search", response_model=list[PatientOut])
def search_patients(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    from sqlalchemy import or_
    q_clean = q.strip()
    if not q_clean:
        return []
    
    search_term = f"%{q_clean}%"
    patients = db.query(Patient).filter(
        or_(
            Patient.prenom.ilike(search_term),
            Patient.nom.ilike(search_term),
            (Patient.prenom + " " + Patient.nom).ilike(search_term),
            (Patient.nom + " " + Patient.prenom).ilike(search_term)
        )
    ).limit(20).all()
    
    return patients


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable.")
    return patient


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable.")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(patient, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Numero WhatsApp deja utilise.") from exc

    db.refresh(patient)
    
    log_activity(db, current_user.nom_utilisateur, f"Modification du patient #{patient.id} ({(patient.nom or '').upper()} {patient.prenom or ''})")
    
    return patient


@router.delete("/{patient_id}", status_code=204)
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable.")

    p_name = f"{(patient.nom or '').upper()} {patient.prenom or ''}"
    db.delete(patient)
    db.commit()
    
    log_activity(db, current_user.nom_utilisateur, f"Suppression du patient #{patient_id} ({p_name})")
    
    return None
