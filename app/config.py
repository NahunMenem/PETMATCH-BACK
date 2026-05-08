from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://petmatch:petmatch123@localhost:5432/petmatch_db"
    APP_TIMEZONE: str = "America/Argentina/Buenos_Aires"
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    GOOGLE_CLIENT_ID: str = ""
    APPLE_BUNDLE_ID: str = "com.petmatch.petmatch"
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CORS_ORIGINS: str = "http://localhost:3000,http://10.0.2.2"
    BREVO_API_KEY: str = ""
    LANDING_URL: str = "https://pawmatch.com.ar"
    MERCADO_PAGO_ACCESS_TOKEN: str = ""
    MERCADO_PAGO_WEBHOOK_SECRET: str = ""
    MERCADO_PAGO_BACK_URL_SUCCESS: str = "petmatch://patitas/success"
    MERCADO_PAGO_BACK_URL_FAILURE: str = "petmatch://patitas/failure"
    MERCADO_PAGO_BACK_URL_PENDING: str = "petmatch://patitas/pending"
    MERCADO_PAGO_NOTIFICATION_URL: str = (
        "https://petmatch-back-production.up.railway.app/webhook-mercadopago"
    )
    MIN_IOS_VERSION: str = "1.0.0"
    MIN_ANDROID_VERSION: str = "1.0.0"
    LATEST_IOS_VERSION: str = "1.0.0"
    LATEST_ANDROID_VERSION: str = "1.0.0"
    FORCE_UPDATE_IOS: bool = False
    FORCE_UPDATE_ANDROID: bool = False
    APP_STORE_URL: str = (
        "https://apps.apple.com/search?term=PawMatch&entity=software"
    )
    PLAY_STORE_URL: str = (
        "https://play.google.com/store/apps/details?id=com.petmatch.petmatch"
    )
    UPDATE_MESSAGE: str = (
        "Hay una nueva versión de PawMatch. Actualizá la app para seguir usando todas las funciones."
    )

    PUBLIC_WEB_URL: str = "https://pawmatch.com.ar"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "PawMatch"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
