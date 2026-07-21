from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from app.models import RendezVous, DisponibiliteMedecin, DefiOtp, Patient, Resultat


DEFAULT_PATIENT_PREFIX = "whatsapp:+999999"
DEFAULT_DOCTOR_PREFIX = "Dr Smoke"
DEFAULT_STORAGE_DIR = Path("storage/encrypted-results")


def remove_file(path_value: str | None) -> None:
    if not path_value:
        return
    path = Path(path_value)
    if path.exists():
        path.unlink(missing_ok=True)


def _delete_appointments(db, appointments: Iterable[RendezVous]) -> None:
    for appointment in appointments:
        if appointment.disponibilite_id is not None:
            availability = db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id == appointment.disponibilite_id).first()
            if availability is not None:
                availability.est_disponible = True
                availability.est_bloque = False
                availability.motif_blocage = None
        db.delete(appointment)


def cleanup_test_data(
    db,
    *,
    patient_ids: list[int] | None = None,
    result_ids: list[int] | None = None,
    availability_ids: list[int] | None = None,
    appointment_ids: list[int] | None = None,
    whatsapp_prefix: str = DEFAULT_PATIENT_PREFIX,
    doctor_prefix: str = DEFAULT_DOCTOR_PREFIX,
) -> None:
    patient_ids = patient_ids or []
    result_ids = result_ids or []
    availability_ids = availability_ids or []
    appointment_ids = appointment_ids or []

    # Delete appointments first so slots can be released cleanly.
    explicit_appointments = [
        appointment
        for appointment in db.query(RendezVous).filter(RendezVous.id.in_(appointment_ids)).all()
    ]
    pattern_appointments = [
        appointment
        for appointment in db.query(RendezVous)
        .filter(RendezVous.nom_medecin.like(f"{doctor_prefix}%"))
        .all()
    ]
    _delete_appointments(db, {appt.id: appt for appt in explicit_appointments + pattern_appointments}.values())
    db.flush()

    # Delete results and their encrypted files.
    explicit_results = [result for result in db.query(Resultat).filter(Resultat.id.in_(result_ids)).all()]
    pattern_results = [
        result
        for result in db.query(Resultat)
        .join(Patient, Resultat.patient_id == Patient.id)
        .filter(Patient.numero_whatsapp.like(f"{whatsapp_prefix}%"))
        .all()
    ]
    for result in {result.id: result for result in explicit_results + pattern_results}.values():
        remove_file(result.chemin_fichier)
        db.delete(result)
    db.flush()

    # Delete OTP challenges tied to smoke-test numbers.
    challenges = (
        db.query(DefiOtp)
        .filter(DefiOtp.numero_whatsapp.like(f"{whatsapp_prefix}%"))
        .all()
    )
    for challenge in challenges:
        db.delete(challenge)
    db.flush()

    # Delete availabilities.
    explicit_availabilities = [
        availability
        for availability in db.query(DisponibiliteMedecin).filter(DisponibiliteMedecin.id.in_(availability_ids)).all()
    ]
    pattern_availabilities = [
        availability
        for availability in db.query(DisponibiliteMedecin)
        .filter(DisponibiliteMedecin.nom_medecin.like(f"{doctor_prefix}%"))
        .all()
    ]
    for availability in {availability.id: availability for availability in explicit_availabilities + pattern_availabilities}.values():
        db.delete(availability)
    db.flush()

    # Delete patients last.
    explicit_patients = [patient for patient in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()]
    pattern_patients = [
        patient
        for patient in db.query(Patient)
        .filter(Patient.numero_whatsapp.like(f"{whatsapp_prefix}%"))
        .all()
    ]
    for patient in {patient.id: patient for patient in explicit_patients + pattern_patients}.values():
        db.delete(patient)

    db.commit()


def purge_storage_dir(storage_dir: str = str(DEFAULT_STORAGE_DIR)) -> None:
    path = Path(storage_dir)
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_file():
            child.unlink(missing_ok=True)
