from datetime import date
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from sqlalchemy import text

from app.db import SessionLocal
from app.models import Patient


def main() -> None:
    session = SessionLocal()
    try:
        # 1) Basic connectivity check
        session.execute(text("SELECT 1"))

        # 2) Insert + read inside a transaction, then rollback
        phone = "whatsapp:+9999990001"
        patient = Patient(
            numero_whatsapp=phone,
            prenom="Smoke",
            nom="Test",
            date_naissance=date(2000, 1, 1),
        )
        session.add(patient)
        session.flush()

        fetched = (
            session.query(Patient)
            .filter(Patient.numero_whatsapp == phone)
            .first()
        )
        if fetched is None:
            raise RuntimeError("Insert/read test failed: patient not found")

        # Force rollback by raising and handling below.
        raise RuntimeError("ROLLBACK_SMOKE_TEST")
    except RuntimeError as exc:
        if str(exc) != "ROLLBACK_SMOKE_TEST":
            raise
    finally:
        session.rollback()
        session.close()

    print("DB smoke test OK: connect + insert + read + rollback")


if __name__ == "__main__":
    main()
