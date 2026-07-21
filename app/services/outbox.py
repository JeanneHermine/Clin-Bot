import json
import logging
from sqlalchemy.orm import Session
from app.models import JournalMessage
from app.services.message_gateway import get_message_gateway

logger = logging.getLogger(__name__)

def retry_failed_messages(db: Session) -> int:
    """Finds failed message logs (with attempts < 3) and retries sending them.
    Returns the count of successfully sent messages.
    """
    failed_messages = (
        db.query(JournalMessage)
        .filter(JournalMessage.statut == "echoue")
        .filter(JournalMessage.tentatives < 3)
        .all()
    )
    
    if not failed_messages:
        logger.info("No failed messages to retry.")
        return 0

    logger.info("Found %d failed messages to retry.", len(failed_messages))
    success_count = 0
    gateway = get_message_gateway()

    for msg in failed_messages:
        msg.tentatives += 1
        media_urls = None
        if msg.urls_media:
            try:
                media_urls = json.loads(msg.urls_media)
            except Exception:
                logger.exception("Failed to parse media_urls for log %d", msg.id)

        try:
            logger.info("Retrying sending message %d to %s (attempt %d)", msg.id, msg.numero_destinataire, msg.tentatives)
            res = gateway.send_whatsapp(msg.numero_destinataire, msg.corps, media_urls)
            msg.statut = "envoye"
            if res and "sid" in res:
                msg.sid_externe = res["sid"]
            success_count += 1
            logger.info("Message %d successfully resent (sid: %s)", msg.id, msg.sid_externe)
        except Exception as e:
            logger.warning("Retry attempt %d failed for message %d: %s", msg.tentatives, msg.id, str(e))
            msg.statut = "echoue"
            
        db.commit()

    return success_count
