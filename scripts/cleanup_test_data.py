import os
import sys

from cryptography.fernet import Fernet

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

from app.db import SessionLocal
from scripts.test_support import cleanup_test_data, purge_storage_dir


def main() -> None:
    db = SessionLocal()
    try:
        cleanup_test_data(db)
        purge_storage_dir()
        print("Cleanup OK: test data removed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
