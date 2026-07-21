#!/usr/bin/env python3
import os
import sys
import logging

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.services.outbox import retry_failed_messages

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("retry_messages_script")

def main():
    logger.info("Starting failed messages retry job...")
    db = SessionLocal()
    try:
        success_count = retry_failed_messages(db)
        logger.info("Failed messages retry job finished. Successfully sent %d messages.", success_count)
    except Exception as e:
        logger.exception("Error occurred while retrying failed messages: %s", str(e))
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
