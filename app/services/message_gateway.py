import json
import logging
from datetime import datetime
from typing import List, Optional

from app.config import settings
from app.db import SessionLocal
from app.models import JournalMessage

logger = logging.getLogger(__name__)


class MessageGateway:
    def send_whatsapp(self, to_number: str, body: str, media_urls: Optional[List[str]] = None):
        raise NotImplementedError()

    def send_sms(self, to_number: str, body: str):
        raise NotImplementedError()


class StubGateway(MessageGateway):
    """Simulation gateway used when Twilio is disabled.

    Behavior:
    - Logs the message
    - Appends a JSON record to `twilio_simulation.log` in project root
    """

    log_path = "twilio_simulation.log"

    def send_whatsapp(self, to_number: str, body: str, media_urls: Optional[List[str]] = None):
        is_failure = "fail" in to_number or to_number.endswith("555")
        
        record = {
            "to": to_number,
            "body": body,
            "media_urls": media_urls or [],
            "via": "stub",
            "ts": datetime.utcnow().isoformat() + "Z",
            "status": "failed" if is_failure else "sent",
        }
        logger.info("[StubGateway] send_whatsapp: %s", record)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write stub message log")

        sid = f"stub-{int(datetime.utcnow().timestamp())}"
        try:
            db = SessionLocal()
            db_record = JournalMessage(
                numero_destinataire=to_number,
                corps=body,
                urls_media=json.dumps(media_urls or []),
                via="stub",
                sid_externe=sid,
                statut="echoue" if is_failure else "envoye",
                tentatives=1,
            )
            db.add(db_record)
            db.commit()
            db.refresh(db_record)
            db.close()
            if is_failure:
                raise Exception("Simulated message transmission error (stub)")
            return {"sid": db_record.sid_externe}
        except Exception as e:
            if is_failure:
                raise e
            logger.exception("Failed to persist stub message to DB")
            return {"sid": sid}

    def send_sms(self, to_number: str, body: str):
        is_failure = "fail" in to_number or to_number.endswith("555")
        clean_number = to_number.replace("whatsapp:", "")
        
        record = {
            "to": clean_number,
            "body": body,
            "via": "stub-sms",
            "ts": datetime.utcnow().isoformat() + "Z",
            "status": "failed" if is_failure else "sent",
        }
        logger.info("[StubGateway] send_sms: %s", record)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write stub sms log")

        sid = f"stub-sms-{int(datetime.utcnow().timestamp())}"
        try:
            db = SessionLocal()
            db_record = JournalMessage(
                numero_destinataire=clean_number,
                corps=body,
                urls_media=json.dumps([]),
                via="stub-sms",
                sid_externe=sid,
                statut="echoue" if is_failure else "envoye",
                tentatives=1,
            )
            db.add(db_record)
            db.commit()
            db.refresh(db_record)
            db.close()
            if is_failure:
                raise Exception("Simulated message transmission error (stub sms)")
            return {"sid": db_record.sid_externe}
        except Exception as e:
            if is_failure:
                raise e
            logger.exception("Failed to persist stub sms to DB")
            return {"sid": sid}


class TwilioGateway(MessageGateway):
    def __init__(self):
        try:
            from twilio.rest import Client

            self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        except Exception:
            logger.exception("Twilio client not available; falling back to stub")
            self.client = None

    def send_whatsapp(self, to_number: str, body: str, media_urls: Optional[List[str]] = None):
        if not self.client:
            return StubGateway().send_whatsapp(to_number, body, media_urls)

        is_failure = "fail" in to_number or to_number.endswith("555")
        sid = f"twilio-mock-{int(datetime.utcnow().timestamp())}"

        if is_failure:
            exc = Exception("Simulated message transmission error (twilio)")
            try:
                db = SessionLocal()
                db_record = JournalMessage(
                    numero_destinataire=to_number,
                    corps=body,
                    urls_media=json.dumps(media_urls or []),
                    via="twilio",
                    sid_externe=f"failed-{sid}",
                    statut="echoue",
                    tentatives=1,
                )
                db.add(db_record)
                db.commit()
                db.close()
            except Exception:
                logger.exception("Failed to persist failed twilio message to DB")
            raise exc

        params = {
            "body": body,
            "from_": settings.twilio_whatsapp_number,
            "to": to_number,
        }
        if media_urls:
            params["media_url"] = media_urls

        try:
            message = self.client.messages.create(**params)
            sid = getattr(message, "sid", None) or sid
        except Exception as e:
            logger.exception("Twilio sending failed, storing as failed log")
            try:
                db = SessionLocal()
                db_record = JournalMessage(
                    numero_destinataire=to_number,
                    corps=body,
                    urls_media=json.dumps(media_urls or []),
                    via="twilio",
                    sid_externe=f"failed-twilio-{int(datetime.utcnow().timestamp())}",
                    statut="echoue",
                    tentatives=1,
                )
                db.add(db_record)
                db.commit()
                db.close()
            except Exception:
                logger.exception("Failed to persist failed twilio message to DB")
            raise e

        try:
            db = SessionLocal()
            db_record = JournalMessage(
                numero_destinataire=to_number,
                corps=body,
                urls_media=json.dumps(media_urls or []),
                via="twilio",
                sid_externe=sid,
                statut="envoye",
                tentatives=1,
            )
            db.add(db_record)
            db.commit()
            db.close()
        except Exception:
            logger.exception("Failed to persist twilio message to DB")

        return {"sid": sid}

    def send_sms(self, to_number: str, body: str):
        if not self.client:
            return StubGateway().send_sms(to_number, body)

        is_failure = "fail" in to_number or to_number.endswith("555")
        clean_number = to_number.replace("whatsapp:", "")
        sid = f"twilio-sms-mock-{int(datetime.utcnow().timestamp())}"

        if is_failure:
            exc = Exception("Simulated message transmission error (twilio sms)")
            try:
                db = SessionLocal()
                db_record = JournalMessage(
                    numero_destinataire=clean_number,
                    corps=body,
                    urls_media=json.dumps([]),
                    via="twilio-sms",
                    sid_externe=f"failed-{sid}",
                    statut="echoue",
                    tentatives=1,
                )
                db.add(db_record)
                db.commit()
                db.close()
            except Exception:
                logger.exception("Failed to persist failed twilio sms to DB")
            raise exc

        # Read configured SMS sender number, or fallback to Twilio WhatsApp number without 'whatsapp:' prefix
        from_number = getattr(settings, "twilio_sms_number", None) or settings.twilio_whatsapp_number.replace("whatsapp:", "")
        params = {
            "body": body,
            "from_": from_number,
            "to": clean_number,
        }

        try:
            message = self.client.messages.create(**params)
            sid = getattr(message, "sid", None) or sid
        except Exception as e:
            logger.exception("Twilio SMS sending failed, storing as failed log")
            try:
                db = SessionLocal()
                db_record = JournalMessage(
                    numero_destinataire=clean_number,
                    corps=body,
                    urls_media=json.dumps([]),
                    via="twilio-sms",
                    sid_externe=f"failed-sms-{int(datetime.utcnow().timestamp())}",
                    statut="echoue",
                    tentatives=1,
                )
                db.add(db_record)
                db.commit()
                db.close()
            except Exception:
                logger.exception("Failed to persist failed twilio sms to DB")
            raise e

        try:
            db = SessionLocal()
            db_record = JournalMessage(
                numero_destinataire=clean_number,
                corps=body,
                urls_media=json.dumps([]),
                via="twilio-sms",
                sid_externe=sid,
                statut="envoye",
                tentatives=1,
            )
            db.add(db_record)
            db.commit()
            db.close()
        except Exception:
            logger.exception("Failed to persist twilio sms to DB")

        return {"sid": sid}


def get_message_gateway() -> MessageGateway:
    if settings.twilio_enabled:
        return TwilioGateway()
    return StubGateway()
