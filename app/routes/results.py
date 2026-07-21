from datetime import date
from pathlib import Path

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Patient, Resultat, Utilisateur
from app.schemas import ResultatOut, ResultatUpdate, SecureResultRetrieveIn, ManualResultCreate
from app.services.otp_service import consume_otp_or_raise
from app.services.upload_security import (
    build_fernet,
    decrypt_file_from_path,
    encrypt_and_store_file,
    infer_content_type_from_encrypted_path,
    infer_original_extension_from_encrypted_path,
)
from app.services.auth_service import require_user, log_activity
from app.services.pdf_generator import generate_medical_pdf


router = APIRouter(prefix="/results", tags=["results"])


@router.post("/upload")
async def upload_result(
    patient_id: int = Form(...),
    analysis_type: str = Form("inconnu"),
    analysis_date: date | None = Form(default=None),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable.")

    file_bytes = await upload.read()
    content_type = upload.content_type or ""

    try:
        fernet = build_fernet(settings.fernet_key)
        encrypted_path = await encrypt_and_store_file(
            raw_bytes=file_bytes,
            content_type=content_type,
            fernet=fernet,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Echec de l'upload securise.") from exc

    result = Resultat(
        patient_id=patient_id,
        type_analyse=analysis_type,
        date_analyse=analysis_date,
        chemin_fichier=encrypted_path,
        statut="en_attente",
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    p_name = f"{(patient.nom or '').upper()} {patient.prenom or ''}"
    log_activity(db, current_user.nom_utilisateur, f"Importation du résultat #{result.id} ({analysis_type}) pour le patient #{patient_id} ({p_name})")

    # Notification WhatsApp automatique
    try:
        from app.services.message_gateway import get_message_gateway
        gateway = get_message_gateway()
        date_str = result.date_analyse.strftime("%d/%m/%Y") if result.date_analyse else "-"
        msg = (
            f"Bonjour, un nouveau résultat d'analyse ({result.type_analyse} du {date_str}) "
            "a été ajouté à votre dossier médical. Pour le consulter de manière sécurisée, "
            "veuillez répondre '2' ou 'Résultats' dans cette conversation WhatsApp."
        )
        gateway.send_whatsapp(patient.numero_whatsapp, msg)
    except Exception as e:
        print(f"[Warning] Impossible d'envoyer la notification de résultat au patient : {e}", flush=True)

    return {
        "result_id": result.id,
        "patient_id": result.patient_id,
        "analysis_type": result.type_analyse,
        "analysis_date": str(result.date_analyse) if result.date_analyse else None,
        "status": result.statut,
        "stored_file_path": result.chemin_fichier,
        "encrypted": True,
    }


@router.post("/create-manual")
async def create_manual_result(
    payload: ManualResultCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    if current_user.role == "doctor":
        raise HTTPException(status_code=403, detail="Les medecins ne peuvent pas creer de resultats d'analyses.")

    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable.")

    p_name = f"{patient.nom} {patient.prenom}"
    p_dob = str(patient.date_naissance) if patient.date_naissance else "Inconnu"
    p_whatsapp = patient.numero_whatsapp.replace("whatsapp:", "")

    try:
        pdf_bytes = generate_medical_pdf(
            patient_name=p_name,
            patient_dob=p_dob,
            patient_whatsapp=p_whatsapp,
            patient_id=patient.id,
            analysis_type=payload.type_analyse,
            analysis_date=str(payload.date_analyse),
            template_type=payload.template_type,
            results_data=payload.results_data,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur de generation PDF: {str(exc)}") from exc

    try:
        fernet = build_fernet(settings.fernet_key)
        encrypted_path = await encrypt_and_store_file(
            raw_bytes=pdf_bytes,
            content_type="application/pdf",
            fernet=fernet,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Echec du stockage securise.") from exc

    result = Resultat(
        patient_id=payload.patient_id,
        type_analyse=payload.type_analyse,
        date_analyse=payload.date_analyse,
        chemin_fichier=encrypted_path,
        statut="en_attente",
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    p_full_display = f"{(patient.nom or '').upper()} {patient.prenom or ''}"
    log_activity(db, current_user.nom_utilisateur, f"Generation manuelle du resultat #{result.id} ({payload.type_analyse}) pour le patient #{payload.patient_id} ({p_full_display})")

    # Notification WhatsApp automatique
    try:
        from app.services.message_gateway import get_message_gateway
        gateway = get_message_gateway()
        date_str = result.date_analyse.strftime("%d/%m/%Y") if result.date_analyse else "-"
        msg = (
            f"Bonjour, un nouveau résultat d'analyse ({result.type_analyse} du {date_str}) "
            "a été généré dans votre dossier médical. Pour le consulter de manière sécurisée, "
            "veuillez répondre '2' ou 'Résultats' dans cette conversation WhatsApp."
        )
        gateway.send_whatsapp(patient.numero_whatsapp, msg)
    except Exception as e:
        print(f"[Warning] Impossible d'envoyer la notification de résultat au patient : {e}", flush=True)

    return {
        "result_id": result.id,
        "patient_id": result.patient_id,
        "analysis_type": result.type_analyse,
        "analysis_date": str(result.date_analyse) if result.date_analyse else None,
        "status": result.statut,
        "stored_file_path": result.chemin_fichier,
        "encrypted": True,
    }


@router.get("", response_model=list[ResultatOut])
def list_results(
    patient_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    query = db.query(Resultat)
    if patient_id is not None:
        query = query.filter(Resultat.patient_id == patient_id)
    return query.order_by(Resultat.id.desc()).all()


@router.get("/{result_id}", response_model=ResultatOut)
def get_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    result = db.query(Resultat).filter(Resultat.id == result_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Resultat introuvable.")
    return result


@router.patch("/{result_id}", response_model=ResultatOut)
def update_result(
    result_id: int,
    payload: ResultatUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    result = db.query(Resultat).filter(Resultat.id == result_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Resultat introuvable.")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(result, key, value)

    db.commit()
    db.refresh(result)
    
    log_activity(db, current_user.nom_utilisateur, f"Modification du résultat #{result_id} (statut: {result.statut})")
    
    return result


@router.delete("/{result_id}", status_code=204)
def delete_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    result = db.query(Resultat).filter(Resultat.id == result_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Resultat introuvable.")

    stored_path = result.chemin_fichier
    db.delete(result)
    db.commit()

    # Best-effort cleanup of encrypted file.
    if stored_path:
        if stored_path.startswith("http://") or stored_path.startswith("https://"):
            from app.config import settings
            if settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret:
                try:
                    import cloudinary
                    import cloudinary.uploader
                    cloudinary.config(
                        cloud_name=settings.cloudinary_cloud_name,
                        api_key=settings.cloudinary_api_key,
                        api_secret=settings.cloudinary_api_secret,
                        secure=True
                    )
                    idx = stored_path.find("encrypted-results/")
                    if idx != -1:
                        public_id = stored_path[idx:]
                        cloudinary.uploader.destroy(public_id, resource_type="raw")
                except Exception:
                    pass
        else:
            path_obj = Path(stored_path)
            if path_obj.exists():
                path_obj.unlink(missing_ok=True)

    log_activity(db, current_user.nom_utilisateur, f"Suppression définitive du résultat #{result_id}")

    return None


@router.post("/retrieve-secure")
def retrieve_result_secure(payload: SecureResultRetrieveIn, db: Session = Depends(get_db)):
    result = db.query(Resultat).filter(Resultat.id == payload.result_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Resultat introuvable.")

    patient = db.query(Patient).filter(Patient.id == result.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient introuvable pour ce resultat.")
    if patient.numero_whatsapp != payload.numero_whatsapp:
        raise HTTPException(status_code=403, detail="Ce resultat ne correspond pas a ce numero WhatsApp.")

    consume_otp_or_raise(
        db,
        secret_key=settings.secret_key,
        whatsapp_number=payload.numero_whatsapp,
        purpose=payload.objectif,
        code=payload.otp_code,
    )

    try:
        fernet = build_fernet(settings.fernet_key)
        decrypted_bytes = decrypt_file_from_path(result.chemin_fichier, fernet)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fichier resultat introuvable.") from exc
    except InvalidToken as exc:
        raise HTTPException(status_code=500, detail="Impossible de dechiffrer le fichier resultat.") from exc

    result.statut = "envoye"
    db.commit()

    extension = infer_original_extension_from_encrypted_path(result.chemin_fichier)
    media_type = infer_content_type_from_encrypted_path(result.chemin_fichier)
    filename = f"result_{result.id}{extension}"

    return Response(
        content=decrypted_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{result_id}/download")
def download_result_admin(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user),
):
    result = db.query(Resultat).filter(Resultat.id == result_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Resultat introuvable.")

    try:
        fernet = build_fernet(settings.fernet_key)
        decrypted_bytes = decrypt_file_from_path(result.chemin_fichier, fernet)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de dechiffrer le fichier.") from exc

    extension = infer_original_extension_from_encrypted_path(result.chemin_fichier)
    media_type = infer_content_type_from_encrypted_path(result.chemin_fichier)
    filename = f"result_{result.id}{extension}"

    return Response(
        content=decrypted_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
