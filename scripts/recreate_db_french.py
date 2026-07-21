import os
import sys
from sqlalchemy import text

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.db import engine, Base
# Import all models to register them with Base
from app.models import Patient, Resultat, RendezVous, DisponibiliteMedecin, SessionChat, DefiOtp, JournalMessage, Utilisateur, JournalAudit

def main():
    print("[DB RECREATE] Connexion à la base de données...")
    with engine.begin() as conn:
        print("[DB RECREATE] Suppression du schéma public...")
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
    
    print("[DB RECREATE] Création de toutes les tables avec le nouveau schéma français...")
    Base.metadata.create_all(bind=engine)
    print("[DB RECREATE] Base de données recréée avec succès.")

if __name__ == "__main__":
    main()
