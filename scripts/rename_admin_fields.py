import os

FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../app/routes/admin.py"))

replacements = [
    # Imports & classes Python
    ("from app.models import User, AuditLog", "from app.models import Utilisateur, JournalAudit"),
    ("current_user: User", "current_user: Utilisateur"),
    ("db.query(User)", "db.query(Utilisateur)"),
    ("db.query(AuditLog)", "db.query(JournalAudit)"),
    ("existing = db.query(User).filter(User.username == payload.username).first()", "existing = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == payload.nom_utilisateur).first()"),
    ("user = User(", "user = Utilisateur("),
    ("username=payload.username", "nom_utilisateur=payload.nom_utilisateur"),
    ("password_hash=hashed", "mot_de_passe_hashe=hashed"),
    ("phone_number=payload.phone_number", "numero_telephone=payload.numero_telephone"),
    ("current_user.username", "current_user.nom_utilisateur"),
    ("user.username", "user.nom_utilisateur"),
    ("user = db.query(User).filter(User.id == user_id).first()", "user = db.query(Utilisateur).filter(Utilisateur.id == user_id).first()"),
    ("username = user.username", "username = user.nom_utilisateur"),
    ("db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()", "db.query(JournalAudit).order_by(JournalAudit.cree_le.desc()).limit(limit).all()"),
    ("user = db.query(User).filter(User.username == payload.username).first()", "user = db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == payload.nom_utilisateur).first()"),
    ("verify_password(payload.password, user.password_hash)", "verify_password(payload.mot_de_passe, user.mot_de_passe_hashe)"),
    ("sign_session(user.username, settings.secret_key)", "sign_session(user.nom_utilisateur, settings.secret_key)"),
    ("return {\"status\": \"ok\", \"role\": user.role, \"username\": user.username}", "return {\"status\": \"ok\", \"role\": user.role, \"username\": user.nom_utilisateur}"),
    ('user_json = json.dumps({\n        "username": current_user.username,\n        "role": current_user.role,\n        "id": current_user.id\n    })', 'user_json = json.dumps({\n        "nom_utilisateur": current_user.nom_utilisateur,\n        "role": current_user.role,\n        "id": current_user.id\n    })'),
    ('window.currentUser = __CURRENT_USER_JSON__;', 'window.currentUser = __CURRENT_USER_JSON__;'),
    
    # HTML forms input name attributes
    ('name="first_name"', 'name="prenom"'),
    ('name="last_name"', 'name="nom"'),
    ('name="whatsapp_number"', 'name="numero_whatsapp"'),
    ('name="secondary_phone_number"', 'name="numero_telephone_secondaire"'),
    ('name="date_of_birth"', 'name="date_naissance"'),
    ('name="doctor_name"', 'name="nom_medecin"'),
    ('name="specialty"', 'name="specialite"'),
    ('name="start_time"', 'name="heure_debut"'),
    ('name="end_time"', 'name="heure_fin"'),
    ('name="username"', 'name="nom_utilisateur"'),
    ('name="password"', 'name="mot_de_passe"'),
    ('name="phone_number"', 'name="numero_telephone"'),
    
    # Javascript payload properties
    ('p.first_name', 'p.prenom'),
    ('p.last_name', 'p.nom'),
    ('p.whatsapp_number', 'p.numero_whatsapp'),
    ('p.date_of_birth', 'p.date_naissance'),
    ('p.secondary_phone_number', 'p.numero_telephone_secondaire'),
    ('p.created_at', 'p.cree_le'),
    
    ('app.doctor_name', 'app.nom_medecin'),
    ('app.specialty', 'app.specialite'),
    ('app.start_time', 'app.heure_debut'),
    ('app.end_time', 'app.heure_fin'),
    ('app.status', 'app.statut'),
    ('app.motif', 'app.motif'),
    ('app.reminder_sent', 'app.rappel_envoye'),
    ('app.requester_first_name', 'app.demandeur_prenom'),
    ('app.requester_last_name', 'app.demandeur_nom'),
    ('app.requester_age', 'app.demandeur_age'),
    ('app.contact_phone_number', 'app.numero_telephone_contact'),
    
    ('r.analysis_type', 'r.type_analyse'),
    ('r.analysis_date', 'r.date_analyse'),
    ('r.file_path', 'r.chemin_fichier'),
    ('r.status', 'r.statut'),
    ('r.created_at', 'r.cree_le'),
    
    ('s.doctor_name', 's.nom_medecin'),
    ('s.specialty', 's.specialite'),
    ('s.start_time', 's.heure_debut'),
    ('s.end_time', 's.heure_fin'),
    ('s.is_available', 's.est_disponible'),
    ('s.is_blocked', 's.est_bloque'),
    ('s.block_reason', 's.motif_blocage'),
    
    ('u.username', 'u.nom_utilisateur'),
    ('u.phone_number', 'u.numero_telephone'),
    ('u.created_at', 'u.cree_le'),
    
    ('l.username', 'l.nom_utilisateur'),
    ('l.action', 'l.action'),
    ('l.details', 'l.details'),
    ('l.created_at', 'l.cree_le'),
    
    # currentUser check in JS
    ('window.currentUser.username', 'window.currentUser.nom_utilisateur'),
    ('username = window.currentUser.username', 'username = window.currentUser.nom_utilisateur'),
    ('username: username', 'nom_utilisateur: username'),
    
    # Status translations in JS
    ("app.status === 'confirmed'", "app.statut === 'confirme'"),
    ("app.status === 'pending_validation'", "app.statut === 'en_attente'"),
    ("r.status === 'envoye'", "r.statut === 'envoye'"),
    ("r.status === 'en_attente'", "r.statut === 'en_attente'"),
    ("filter === 'pending_validation'", "filter === 'en_attente'"),
    ("filter === 'confirmed'", "filter === 'confirme'"),
    ("filter === 'cancelled'", "filter === 'annule'"),
    ("filter === 'rejected'", "filter === 'rejete'"),
    
    ("updateAppointmentStatus(${app.id}, 'confirmed')", "updateAppointmentStatus(${app.id}, 'confirme')"),
    ("updateAppointmentStatus(${app.id}, 'rejected')", "updateAppointmentStatus(${app.id}, 'rejete')"),
    ("updateAppointmentStatus(${app.id}, 'cancelled')", "updateAppointmentStatus(${app.id}, 'annule')"),
    
    # Body object mappings in JS modal
    ("body: JSON.stringify({ is_blocked: false, is_available: true, block_reason: null })", "body: JSON.stringify({ est_bloque: false, est_disponible: true, motif_blocage: null })"),
    
    # Miscellaneous / other UI details
    ("app.status === 'confirmed' ? 'Confirmé' : 'En attente'", "app.statut === 'confirme' ? 'Confirmé' : 'En attente'"),
    ("app.patient_id", "app.patient_id"),
]

def main():
    print(f"Reading file: {FILE_PATH}...")
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Apply replacements
    for old, new in replacements:
        content = content.replace(old, new)
        
    # Also manual python replacements for user_json format
    content = content.replace('"username": current_user.username,', '"nom_utilisateur": current_user.nom_utilisateur,')
    content = content.replace("userEl.textContent = '@' + window.currentUser.username", "userEl.textContent = '@' + window.currentUser.nom_utilisateur")
    
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Refactoring complete for {FILE_PATH}.")

if __name__ == "__main__":
    main()
