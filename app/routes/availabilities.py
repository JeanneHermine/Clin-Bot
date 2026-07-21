from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DisponibiliteMedecin, Utilisateur
from app.schemas import DisponibiliteMedecinCreate, DisponibiliteMedecinOut, DisponibiliteMedecinUpdate
from app.services.auth_service import require_user, log_activity
from app.services.cache import invalidate_availabilities_cache


router = APIRouter(prefix="/availabilities", tags=["availabilities"])


@router.post("", response_model=DisponibiliteMedecinOut, status_code=201)
def create_availability(
    payload: DisponibiliteMedecinCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    availability = DisponibiliteMedecin(**payload.model_dump())
    db.add(availability)
    db.commit()
    db.refresh(availability)
    invalidate_availabilities_cache()
    
    log_activity(db, current_user.nom_utilisateur, f"Création du créneau #{availability.id} pour le Dr {availability.nom_medecin} ({availability.specialite})")
    
    return availability


@router.get("", response_model=list[DisponibiliteMedecinOut])
def list_availabilities(
    doctor_name: str | None = Query(default=None),
    specialty: str | None = Query(default=None),
    only_available: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    query = db.query(DisponibiliteMedecin)
    if doctor_name:
        query = query.filter(DisponibiliteMedecin.nom_medecin == doctor_name)
    if specialty:
        query = query.filter(DisponibiliteMedecin.specialite == specialty)
    if only_available:
        query = query.filter(DisponibiliteMedecin.est_disponible.is_(True), DisponibiliteMedecin.est_bloque.is_(False))
    return query.order_by(DisponibiliteMedecin.heure_debut.asc()).all()


@router.get("/{availability_id}", response_model=DisponibiliteMedecinOut)
def get_availability(
    availability_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == availability_id).first()
    if availability is None:
        raise HTTPException(status_code=404, detail="Creneau introuvable.")
    return availability


@router.patch("/{availability_id}", response_model=DisponibiliteMedecinOut)
def update_availability(
    availability_id: int,
    payload: DisponibiliteMedecinUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == availability_id).first()
    if availability is None:
        raise HTTPException(status_code=404, detail="Creneau introuvable.")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(availability, key, value)

    db.commit()
    db.refresh(availability)
    invalidate_availabilities_cache()
    
    status_desc = "bloqué" if availability.est_bloque else "libre/disponible"
    log_activity(db, current_user.nom_utilisateur, f"Modification du créneau #{availability_id} pour le Dr {availability.nom_medecin} (statut: {status_desc})")
    
    return availability


@router.post("/{availability_id}/block", response_model=DisponibiliteMedecinOut)
def block_availability(
    availability_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == availability_id).first()
    if availability is None:
        raise HTTPException(status_code=404, detail="Creneau introuvable.")

    availability.est_disponible = False
    availability.est_bloque = True
    availability.motif_blocage = reason
    db.commit()
    db.refresh(availability)
    invalidate_availabilities_cache()
    
    log_activity(db, current_user.nom_utilisateur, f"Blocage manuel du créneau #{availability_id} pour le Dr {availability.nom_medecin} (motif: {reason or 'non renseigné'})")
    
    return availability


@router.delete("/{availability_id}", status_code=204)
def delete_availability(
    availability_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == availability_id).first()
    if availability is None:
        raise HTTPException(status_code=404, detail="Creneau introuvable.")

    doc = availability.nom_medecin
    db.delete(availability)
    db.commit()
    invalidate_availabilities_cache()
    
    log_activity(db, current_user.nom_utilisateur, f"Suppression du créneau #{availability_id} pour le Dr {doc}")
    
    return None
