from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://pwm_user:pwm_pass@localhost:5432/pwm_db"
    secret_key: str = "changeme"
    fernet_key: str = "change_this_to_a_32_byte_urlsafe_base64"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"
    twilio_enabled: bool = False
    twilio_sandbox_auto_register: bool = False
    otp_expiry_minutes: int = 10
    otp_max_attempts: int = 3
    otp_debug_return_code: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str | None = None

    # Cloudinary storage settings
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # Africa's Talking SMS settings
    africastalking_username: str = ""
    africastalking_api_key: str = ""
    africastalking_sender_id: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def get_public_url(request, name: str, **kwargs) -> str:
    """Generates a URL and overrides its scheme/host with base_url if set."""
    from urllib.parse import urlparse, urlunparse
    url = request.url_for(name, **kwargs)
    if settings.base_url:
        parsed_base = urlparse(settings.base_url)
        parsed_url = urlparse(str(url))
        url = urlunparse(
            (
                parsed_base.scheme or parsed_url.scheme,
                parsed_base.netloc or parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                parsed_url.query,
                parsed_url.fragment,
            )
        )
    return str(url)

