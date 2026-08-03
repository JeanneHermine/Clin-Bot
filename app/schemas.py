from datetime import date, datetime
import re
from pydantic import BaseModel, field_validator


class PatientBase(BaseModel):
    numero_whatsapp: str
    prenom: str | None = None
    nom: str | None = None
    date_naissance: date | None = None
    numero_telephone_secondaire: str | None = None

    @field_validator("numero_whatsapp")
    @classmethod
    def clean_and_normalize_whatsapp(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not v.startswith("whatsapp:"):
            return f"whatsapp:{v}"
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    numero_whatsapp: str | None = None
    prenom: str | None = None
    nom: str | None = None
    date_naissance: date | None = None
    numero_telephone_secondaire: str | None = None

    @field_validator("numero_whatsapp")
    @classmethod
    def clean_and_normalize_whatsapp(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().replace(" ", "")
            if not v.startswith("whatsapp:"):
                return f"whatsapp:{v}"
        return v


class PatientOut(PatientBase):
    id: int
    cree_le: datetime | None = None

    class Config:
        from_attributes = True


class ResultatUpdate(BaseModel):
    type_analyse: str | None = None
    date_analyse: date | None = None
    statut: str | None = None


class ResultatOut(BaseModel):
    id: int
    patient_id: int
    date_analyse: date | None = None
    type_analyse: str | None = None
    chemin_fichier: str
    statut: str
    cree_le: datetime | None = None

    class Config:
        from_attributes = True


class ManualResultCreate(BaseModel):
    patient_id: int
    type_analyse: str
    date_analyse: date
    template_type: str  # blood, urine, lipid, custom
    results_data: dict


class OtpRequestIn(BaseModel):
    numero_whatsapp: str
    objectif: str = "result_access"

    @field_validator("numero_whatsapp")
    @classmethod
    def clean_and_normalize_whatsapp(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not v.startswith("whatsapp:"):
            return f"whatsapp:{v}"
        return v


class OtpRequestOut(BaseModel):
    challenge_id: int
    numero_whatsapp: str
    objectif: str
    expire_le: datetime
    tentatives_max: int
    otp_code: str | None = None


class OtpVerifyIn(BaseModel):
    numero_whatsapp: str
    objectif: str = "result_access"
    code: str

    @field_validator("numero_whatsapp")
    @classmethod
    def clean_and_normalize_whatsapp(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not v.startswith("whatsapp:"):
            return f"whatsapp:{v}"
        return v


class OtpVerifyOut(BaseModel):
    verified: bool
    message: str


class SecureResultRetrieveIn(BaseModel):
    result_id: int
    numero_whatsapp: str
    otp_code: str
    objectif: str = "result_access"

    @field_validator("numero_whatsapp")
    @classmethod
    def clean_and_normalize_whatsapp(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not v.startswith("whatsapp:"):
            return f"whatsapp:{v}"
        return v


class DisponibiliteMedecinBase(BaseModel):
    nom_medecin: str
    specialite: str | None = None
    heure_debut: datetime
    heure_fin: datetime | None = None


class DisponibiliteMedecinCreate(DisponibiliteMedecinBase):
    est_bloque: bool = False
    motif_blocage: str | None = None


class DisponibiliteMedecinUpdate(BaseModel):
    nom_medecin: str | None = None
    specialite: str | None = None
    heure_debut: datetime | None = None
    heure_fin: datetime | None = None
    est_disponible: bool | None = None
    est_bloque: bool | None = None
    motif_blocage: str | None = None


class DisponibiliteMedecinOut(DisponibiliteMedecinBase):
    id: int
    est_disponible: bool
    est_bloque: bool
    motif_blocage: str | None = None
    cree_le: datetime | None = None

    class Config:
        from_attributes = True


class RendezVousBase(BaseModel):
    patient_id: int
    demandeur_prenom: str | None = None
    demandeur_nom: str | None = None
    demandeur_age: int | None = None
    numero_telephone_contact: str | None = None
    nom_medecin: str
    specialite: str | None = None
    heure_debut: datetime
    heure_fin: datetime | None = None
    motif: str | None = None
    rappel_envoye: bool | None = False


class RendezVousCreate(RendezVousBase):
    disponibilite_id: int | None = None


class RendezVousUpdate(BaseModel):
    patient_id: int | None = None
    demandeur_prenom: str | None = None
    demandeur_nom: str | None = None
    demandeur_age: int | None = None
    numero_telephone_contact: str | None = None
    nom_medecin: str | None = None
    specialite: str | None = None
    heure_debut: datetime | None = None
    heure_fin: datetime | None = None
    motif: str | None = None
    statut: str | None = None
    rappel_envoye: bool | None = None


class RendezVousOut(RendezVousBase):
    id: int
    disponibilite_id: int | None = None
    statut: str
    cree_le: datetime | None = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    nom_utilisateur: str
    mot_de_passe: str
    role: str = "staff"
    numero_telephone: str | None = None
    email: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str | None) -> str | None:
        if v is not None:
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", v):
                raise ValueError("Adresse email invalide.")
        return v


class UserLoginIn(BaseModel):
    nom_utilisateur: str
    mot_de_passe: str


class UserOut(BaseModel):
    id: int
    nom_utilisateur: str
    role: str
    numero_telephone: str | None = None
    email: str | None = None
    cree_le: datetime | None = None

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: int
    nom_utilisateur: str
    action: str
    details: str | None = None
    cree_le: datetime | None = None

    class Config:
        from_attributes = True
