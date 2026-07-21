from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JournalMessage, Utilisateur
from app.services.auth_service import require_user

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=List[dict])
def list_messages(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    """Liste les logs de messages WhatsApp. Réservé aux utilisateurs authentifiés."""
    rows = db.query(JournalMessage).order_by(JournalMessage.cree_le.desc()).limit(limit).all()
    result = []
    for r in rows:
        result.append(
            {
                "id": r.id,
                "to_number": r.numero_destinataire,
                "body": r.corps,
                "media_urls": r.urls_media,
                "via": r.via,
                "external_sid": r.sid_externe,
                "status": r.statut,
                "attempts": r.tentatives,
                "created_at": r.cree_le.isoformat() if r.cree_le else None,
            }
        )
    return result
