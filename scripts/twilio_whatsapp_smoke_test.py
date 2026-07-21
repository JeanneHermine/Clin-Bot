import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.config import settings


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python scripts/twilio_whatsapp_smoke_test.py whatsapp:+<numero> [message]"
        )

    to_number = sys.argv[1].strip()
    message_body = sys.argv[2] if len(sys.argv) > 2 else "Bonjour, test WhatsApp Twilio depuis Cid."

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise SystemExit("TWILIO_ACCOUNT_SID et TWILIO_AUTH_TOKEN doivent etre definis dans l'environnement.")

    if not settings.twilio_whatsapp_number:
        raise SystemExit("TWILIO_WHATSAPP_NUMBER doit etre defini dans l'environnement.")

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(
        body=message_body,
        from_=settings.twilio_whatsapp_number,
        to=to_number,
    )

    print(f"Message WhatsApp envoye: {message.sid}")


if __name__ == "__main__":
    main()