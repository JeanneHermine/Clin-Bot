import os
import sys

from cryptography.fernet import Fernet

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

from app.db import SessionLocal
from app.services.reminders import send_upcoming_appointment_reminders


def main() -> None:
    db = SessionLocal()
    try:
        print("Checking and sending reminders...")
        count = send_upcoming_appointment_reminders(db)
        print(f"Task completed. {count} reminder(s) sent.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
