from sqlalchemy import Boolean, Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .db import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    numero_whatsapp = Column(String(32), unique=True, nullable=False, index=True)
    prenom = Column(String(100), nullable=True)
    nom = Column(String(100), nullable=True)
    date_naissance = Column(Date, nullable=True)
    numero_telephone_secondaire = Column(String(32), nullable=True)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    resultats = relationship("Resultat", back_populates="patient", passive_deletes=True)
    rendez_vous = relationship("RendezVous", back_populates="patient", passive_deletes=True)
    defis_otp = relationship(
        "DefiOtp",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Resultat(Base):
    __tablename__ = "resultats"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    date_analyse = Column(Date, nullable=True)
    type_analyse = Column(String(100), nullable=True)
    chemin_fichier = Column(String(512), nullable=False)
    statut = Column(String(32), nullable=False, default="en_attente")
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="resultats")


class RendezVous(Base):
    __tablename__ = "rendez_vous"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    disponibilite_id = Column(Integer, ForeignKey("disponibilites_medecins.id", ondelete="SET NULL"), nullable=True, unique=True)
    demandeur_prenom = Column(String(100), nullable=True)
    demandeur_nom = Column(String(100), nullable=True)
    demandeur_age = Column(Integer, nullable=True)
    numero_telephone_contact = Column(String(32), nullable=True)
    nom_medecin = Column(String(200), nullable=False)
    specialite = Column(String(100), nullable=True)
    heure_debut = Column(DateTime(timezone=True), nullable=False)
    heure_fin = Column(DateTime(timezone=True), nullable=True)
    motif = Column(String(255), nullable=True)
    statut = Column(String(32), nullable=False, default="en_attente")
    rappel_envoye = Column(Boolean, default=False, nullable=False)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="rendez_vous")
    disponibilite = relationship("DisponibiliteMedecin", back_populates="rendez_vous")


class DisponibiliteMedecin(Base):
    __tablename__ = "disponibilites_medecins"

    id = Column(Integer, primary_key=True, index=True)
    nom_medecin = Column(String(200), nullable=False, index=True)
    specialite = Column(String(100), nullable=True, index=True)
    heure_debut = Column(DateTime(timezone=True), nullable=False, index=True)
    heure_fin = Column(DateTime(timezone=True), nullable=True)
    est_disponible = Column(Boolean, nullable=False, default=True)
    est_bloque = Column(Boolean, nullable=False, default=False)
    motif_blocage = Column(String(255), nullable=True)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    rendez_vous = relationship("RendezVous", back_populates="disponibilite", uselist=False, passive_deletes=True)


class SessionChat(Base):
    __tablename__ = "sessions_chat"

    id = Column(Integer, primary_key=True, index=True)
    numero_whatsapp = Column(String(32), nullable=False, index=True)
    etat = Column(String(64), nullable=False, default="menu")
    donnees = Column(Text, nullable=True)
    mis_a_jour_le = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DefiOtp(Base):
    __tablename__ = "defis_otp"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    numero_whatsapp = Column(String(32), nullable=False, index=True)
    objectif = Column(String(64), nullable=False, default="result_access")
    hash_code = Column(String(128), nullable=False)
    expire_le = Column(DateTime(timezone=True), nullable=False)
    tentatives = Column(Integer, nullable=False, default=0)
    tentatives_max = Column(Integer, nullable=False, default=3)
    est_consomme = Column(Boolean, nullable=False, default=False)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    verifie_le = Column(DateTime(timezone=True), nullable=True)

    patient = relationship("Patient", back_populates="defis_otp")


class JournalMessage(Base):
    __tablename__ = "journaux_messages"

    id = Column(Integer, primary_key=True, index=True)
    numero_destinataire = Column(String(64), nullable=False, index=True)
    corps = Column(Text, nullable=True)
    urls_media = Column(Text, nullable=True)
    via = Column(String(32), nullable=True)
    sid_externe = Column(String(128), nullable=True)
    statut = Column(String(32), nullable=False, default="envoye")
    tentatives = Column(Integer, default=1, nullable=False)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id = Column(Integer, primary_key=True, index=True)
    nom_utilisateur = Column(String(100), unique=True, nullable=False, index=True)
    mot_de_passe_hashe = Column(String(256), nullable=False)
    role = Column(String(50), nullable=False, default="staff")  # admin, doctor, laborantin
    numero_telephone = Column(String(32), nullable=True)
    email = Column(String(100), nullable=True)
    token_reinitialisation = Column(String(256), nullable=True)
    expire_token_reinitialisation = Column(DateTime(timezone=True), nullable=True)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())


class JournalAudit(Base):
    __tablename__ = "journaux_audit"

    id = Column(Integer, primary_key=True, index=True)
    nom_utilisateur = Column(String(100), nullable=False, index=True)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
