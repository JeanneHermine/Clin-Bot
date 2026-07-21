import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Generate a temporary Fernet key in case it's not set in the environment
if not os.environ.get("FERNET_KEY"):
    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

from app.db import SessionLocal
from app.models import Patient, Resultat, RendezVous, DisponibiliteMedecin, SessionChat, DefiOtp, JournalMessage, Utilisateur, JournalAudit
from app.services.auth_service import create_default_admin
from scripts.test_support import purge_storage_dir


def main() -> None:
    db = SessionLocal()
    try:
        print("[DB PURGE] Suppression de tous les rendez-vous...")
        db.query(RendezVous).delete()
        
        print("[DB PURGE] Suppression de tous les résultats d'analyses...")
        db.query(Resultat).delete()
        
        print("[DB PURGE] Suppression de tous les défis OTP...")
        db.query(DefiOtp).delete()
        
        print("[DB PURGE] Suppression de tous les patients...")
        db.query(Patient).delete()
        
        print("[DB PURGE] Suppression de toutes les disponibilités des médecins...")
        db.query(DisponibiliteMedecin).delete()
        
        print("[DB PURGE] Suppression de toutes les sessions de chat...")
        db.query(SessionChat).delete()
        
        print("[DB PURGE] Suppression de tous les messages de l'outbox...")
        db.query(JournalMessage).delete()
        
        print("[DB PURGE] Suppression de tous les logs d'audit...")
        db.query(JournalAudit).delete()
        
        print("[DB PURGE] Suppression de tous les utilisateurs (hors admin par défaut)...")
        db.query(Utilisateur).filter(Utilisateur.nom_utilisateur != "admin").delete()
        
        # S'assurer que le compte admin par défaut existe
        create_default_admin(db)
        
        db.commit()
        print("[DB PURGE] Base de données nettoyée avec succès.")
        
        # Purge des fichiers physiques chiffrés
        purge_storage_dir()
        print("[DB PURGE] Dossier de stockage vidé avec succès.")
        
    except Exception as e:
        db.rollback()
        print(f"[DB PURGE] Erreur lors du nettoyage de la base de données : {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
