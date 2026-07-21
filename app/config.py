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

    # Cloudinary storage settings
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")



settings = Settings()
