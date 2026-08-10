import os
import sys
from datetime import datetime, timedelta, timezone

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.db import SessionLocal
from app.models import Patient, DisponibiliteMedecin, RendezVous, Resultat, JournalAudit, Utilisateur
from app.services.auth_service import hash_password

def seed():
    db = SessionLocal()
    try:
        # Check if database already has seed data (e.g. patients)
        if db.query(Patient).count() > 0:
            print("Database already has patient data, skipping seeding.")
            return

        print("Seeding database with realistic medical data...")

        # 1. Create Users with different roles if they don't exist
        users = [
            ("Roméo", "roméo123", "admin"),
            ("Sandra", "sandra123", "staff"),
            ("Nelly", "nelly123", "laborantin"),
            ("Dodds", "dodds123", "doctor")
        ]
        for username, password, role in users:
            if not db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == username).first():
                db.add(Utilisateur(
                    nom_utilisateur=username,
                    mot_de_passe_hashe=hash_password(password),
                    role=role,
                    numero_telephone=f"whatsapp:+336123456{len(username)}"
                ))

        # 2. Create Patients
        patients = [
            Patient(numero_whatsapp="whatsapp:+22997123456", prenom="Kofi", nom="AGBOSSA", date_naissance=datetime.strptime("1985-05-12", "%Y-%m-%d").date()),
            Patient(numero_whatsapp="whatsapp:+22995654321", prenom="Abla", nom="SOGLO", date_naissance=datetime.strptime("1990-11-07", "%Y-%m-%d").date()),
            Patient(numero_whatsapp="whatsapp:+22961894561", prenom="Sena", nom="KODJO", date_naissance=datetime.strptime("1978-02-28", "%Y-%m-%d").date()),
            Patient(numero_whatsapp="whatsapp:+22990112222", prenom="Femi", nom="ADENYI", date_naissance=datetime.strptime("1995-09-15", "%Y-%m-%d").date()),
            Patient(numero_whatsapp="whatsapp:+22997334444", prenom="Yasmine", nom="BIO", date_naissance=datetime.strptime("2000-07-20", "%Y-%m-%d").date())
        ]
        for p in patients:
            db.add(p)
        db.commit()

        # Refresh to get IDs
        for p in patients:
            db.refresh(p)

        # 3. Create Doctor Availabilities
        now = datetime.now(timezone.utc).replace(microsecond=0)
        base_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        doctors = [
            ("Dr. Basile ADJOU", "Cardiologie"),
            ("Dr. Chantal GOLOU", "Pédiatrie"),
            ("Dr. Mathieu KEREKOU", "Dermatologie"),
            ("Dr. Sabine HOUNDEGNON", "Ophtalmologie")
        ]

        availabilities = []
        # Standard daytime slots: 09:00, 10:30, 14:00, 15:30
        slots_config = [
            (0, 9, 0),    # Day +0, 09:00
            (0, 10, 30),  # Day +0, 10:30
            (1, 14, 0),   # Day +1, 14:00
            (1, 15, 30),  # Day +1, 15:30
        ]

        for doc_name, specialty in doctors:
            for day_offset, hour, minute in slots_config:
                start = base_date + timedelta(days=day_offset, hours=hour, minutes=minute)
                end = start + timedelta(minutes=30)
                avail = DisponibiliteMedecin(
                    nom_medecin=doc_name,
                    specialite=specialty,
                    heure_debut=start,
                    heure_fin=end,
                    est_disponible=True
                )
                db.add(avail)
                availabilities.append(avail)
        db.commit()

        for a in availabilities:
            db.refresh(a)

        # 4. Create some Appointments (booking some availabilities)
        # Booking Patient 1 with Doctor 1
        avail_to_book = availabilities[0]
        avail_to_book.est_disponible = False
        appt1 = RendezVous(
            patient_id=patients[0].id,
            disponibilite_id=avail_to_book.id,
            nom_medecin=avail_to_book.nom_medecin,
            specialite=avail_to_book.specialite,
            heure_debut=avail_to_book.heure_debut,
            heure_fin=avail_to_book.heure_fin,
            motif="Consultation annuelle de contrôle cardiaque",
            statut="confirme",
            rappel_envoye=False
        )
        db.add(appt1)

        # Booking Patient 2 with Doctor 2
        avail_to_book2 = availabilities[4]
        avail_to_book2.est_disponible = False
        appt2 = RendezVous(
            patient_id=patients[1].id,
            disponibilite_id=avail_to_book2.id,
            nom_medecin=avail_to_book2.nom_medecin,
            specialite=avail_to_book2.specialite,
            heure_debut=avail_to_book2.heure_debut,
            heure_fin=avail_to_book2.heure_fin,
            motif="Fièvre persistante enfant",
            statut="confirme",
            rappel_envoye=True
        )
        db.add(appt2)

        # 5. Create some Results (medical analysis files)
        results = [
            Resultat(
                patient_id=patients[0].id,
                date_analyse=(now - timedelta(days=5)).date(),
                type_analyse="Bilan Sanguin",
                chemin_fichier="storage/encrypted-results/dummy_result_1.pdf",
                statut="envoye"
            ),
            Resultat(
                patient_id=patients[1].id,
                date_analyse=(now - timedelta(days=2)).date(),
                type_analyse="Bilan Lipidique",
                chemin_fichier="storage/encrypted-results/dummy_result_2.pdf",
                statut="en_attente"
            ),
            Resultat(
                patient_id=patients[2].id,
                date_analyse=(now - timedelta(days=1)).date(),
                type_analyse="Test Urine",
                chemin_fichier="storage/encrypted-results/dummy_result_3.pdf",
                statut="en_attente"
            )
        ]
        for r in results:
            db.add(r)

        # 6. Create Audit Logs
        logs = [
            JournalAudit(nom_utilisateur="Roméo", action="Connexion réussie", details="IP: 127.0.0.1"),
            JournalAudit(nom_utilisateur="Roméo", action="Création du patient #1", details="Nom: AGBOSSA Kofi"),
            JournalAudit(nom_utilisateur="Roméo", action="Création du patient #2", details="Nom: SOGLO Abla"),
            JournalAudit(nom_utilisateur="Roméo", action="Génération PDF Bilan Sanguin", details="Patient ID: 1"),
            JournalAudit(nom_utilisateur="Nelly", action="Téléchargement du résultat d'analyse #1", details="Bilan Sanguin"),
            JournalAudit(nom_utilisateur="Roméo", action="Création de créneaux médecin", details="Dr. Basile ADJOU - Cardiologie")
        ]
        for log in logs:
            db.add(log)

        db.commit()
        print("Database successfully seeded with mock data!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
