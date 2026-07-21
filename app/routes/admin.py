from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Utilisateur, JournalAudit
from app.schemas import UserCreate, UserOut, AuditLogOut, UserLoginIn
from app.services.auth_service import require_user, log_activity, hash_password, get_session_user, verify_password, sign_session
from app.config import settings


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if not user:
        return RedirectResponse(url="/admin/login")

    user_json = f'{{"id": {user.id}, "username": "{user.nom_utilisateur}", "role": "{user.role}"}}'

    import os
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "dashboard.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__CURRENT_USER_JSON__", user_json)
    return HTMLResponse(content=html)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé. Administrateur uniquement.")
    return db.query(Utilisateur).order_by(Utilisateur.id.asc()).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé. Administrateur uniquement.")
    
    # Check if username exists
    existing = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == payload.nom_utilisateur).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà utilisé.")
    
    hashed = hash_password(payload.mot_de_passe)
    user = Utilisateur(
        nom_utilisateur=payload.nom_utilisateur,
        mot_de_passe_hashe=hashed,
        role=payload.role,
        numero_telephone=payload.numero_telephone,
        email=payload.email
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    log_activity(db, current_user.nom_utilisateur, f"Création de l'utilisateur @{user.nom_utilisateur} ({user.role})")
    return user


@router.post("/users/remind-slots")
def remind_doctors_slots(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé. Administrateur uniquement.")
    
    from app.services.reminders import check_and_send_doctor_reminders
    count = check_and_send_doctor_reminders(db)
    
    log_activity(db, current_user.nom_utilisateur, f"Envoi de rappels de créneaux à {count} médecins.")
    return {"message": f"{count} rappels envoyés avec succès."}


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé. Administrateur uniquement.")
    
    user = db.query(Utilisateur).filter(Utilisateur.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    
    # Don't delete self
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte.")
        
    username = user.nom_utilisateur
    db.delete(user)
    db.commit()
    
    log_activity(db, current_user.nom_utilisateur, f"Suppression de l'utilisateur @{username}")
    return None


@router.get("/logs", response_model=list[AuditLogOut])
def list_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé. Administrateur uniquement.")
    return db.query(JournalAudit).order_by(JournalAudit.cree_le.desc()).limit(limit).all()


@router.delete("/logs", status_code=204)
def clear_logs(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé. Administrateur uniquement.")
    db.query(JournalAudit).delete()
    db.commit()
    return None


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if user:
        return RedirectResponse(url="/admin")

    import os
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "login.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html)



@router.post("/login")
def login(payload: UserLoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == payload.nom_utilisateur).first()
    if not user or not verify_password(payload.mot_de_passe, user.mot_de_passe_hashe):
        raise HTTPException(status_code=400, detail="Identifiants incorrects.")

    session_value = sign_session(user.nom_utilisateur, settings.secret_key)
    response.set_cookie(
        key="cid_session",
        value=session_value,
        httponly=True,
        samesite="lax",
        max_age=3600 * 24 * 7  # 1 week
    )
    return {"status": "ok", "role": user.role, "username": user.nom_utilisateur}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="cid_session")
    return {"status": "ok"}


@router.post("/forgot-password")
def forgot_password(payload: dict, db: Session = Depends(get_db)):
    username = payload.get("nom_utilisateur")
    if not username:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur requis.")
    
    user = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == username).first()
    if user and user.email:
        import secrets
        from datetime import datetime, timezone, timedelta
        import json
        from app.models import JournalMessage

        token = secrets.token_urlsafe(32)
        user.token_reinitialisation = token
        user.expire_token_reinitialisation = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()

        reset_link = f"http://localhost:8000/admin/reset-password?token={token}"
        body = (
            f"Bonjour @{user.nom_utilisateur},\n\n"
            f"Vous avez demandé la réinitialisation de votre mot de passe Cid. "
            f"Veuillez cliquer sur le lien suivant pour choisir un nouveau mot de passe (valide 1 heure) :\n"
            f"{reset_link}\n\n"
            f"Si vous n'avez pas demandé ce changement, vous pouvez ignorer cet e-mail."
        )
        
        email_record = {
            "to": user.email,
            "subject": "Réinitialisation de votre mot de passe Cid",
            "body": body,
            "ts": datetime.now(timezone.utc).isoformat() + "Z",
        }
        try:
            with open("email_simulation.log", "a", encoding="utf-8") as f:
                f.write(json.dumps(email_record, ensure_ascii=False) + "\n")
            
            db_record = JournalMessage(
                numero_destinataire=user.email,
                corps=body,
                urls_media=json.dumps([]),
                via="email",
                sid_externe=f"email-reset-{int(datetime.now(timezone.utc).timestamp())}",
                statut="envoye",
                tentatives=1,
            )
            db.add(db_record)
            db.commit()
        except Exception as e:
            print(f"[Warning] Failed to log email reset password: {e}", flush=True)

    return {"message": "Si le compte existe et dispose d'une adresse email, un lien de réinitialisation a été envoyé."}


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(token: str, db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=400, detail="Jeton de réinitialisation requis.")
    
    from datetime import datetime, timezone
    user = db.query(Utilisateur).filter(Utilisateur.token_reinitialisation == token).first()
    if not user:
        return HTMLResponse("<h2>Lien de réinitialisation invalide.</h2>", status_code=400)
        
    expire = user.expire_token_reinitialisation
    if expire.tzinfo is None:
        expire = expire.replace(tzinfo=timezone.utc)
        
    if datetime.now(timezone.utc) > expire:
        return HTMLResponse("<h2>Lien de réinitialisation expiré.</h2>", status_code=400)
    
    import os
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "reset_password.html")
    if not os.path.exists(template_path):
        return HTMLResponse("<h2>Template de réinitialisation introuvable.</h2>", status_code=500)
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__RESET_TOKEN__", token)
    return HTMLResponse(content=html)


@router.post("/reset-password")
def process_reset_password(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    new_password = payload.get("mot_de_passe")
    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Jeton et mot de passe requis.")
        
    from datetime import datetime, timezone
    user = db.query(Utilisateur).filter(Utilisateur.token_reinitialisation == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Jeton de réinitialisation invalide.")
        
    expire = user.expire_token_reinitialisation
    if expire.tzinfo is None:
        expire = expire.replace(tzinfo=timezone.utc)
        
    if datetime.now(timezone.utc) > expire:
        raise HTTPException(status_code=400, detail="Jeton de réinitialisation expiré.")
        
    user.mot_de_passe_hashe = hash_password(new_password)
    user.token_reinitialisation = None
    user.expire_token_reinitialisation = None
    db.commit()
    
    log_activity(db, user.nom_utilisateur, "Réinitialisation réussie du mot de passe.")
    return {"message": "Votre mot de passe a été réinitialisé avec succès."}



