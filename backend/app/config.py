"""Config via env vars."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/meshtostep.db"
    SECRET_KEY: str = "CHANGE-ME-in-production-use-openssl-rand-hex-32"
    FREE_CREDITS: int = 3
    MAX_FILE_MB: int = 200
    FREECAD_CMD: str = "/usr/bin/freecadcmd"  # Docker path
    DATA_DIR: str = "./data"
    CORS_ORIGINS: str = "*"
    APP_NAME: str = "MeshToStep"
    APP_URL: str = "http://localhost:8000"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CURRENCY: str = "usd"
    # -- auth hardening --
    ADMIN_EMAIL: str = ""  # bootstrap admin on first run
    ADMIN_PASSWORD: str = ""
    EMAIL_VERIFICATION_REQUIRED: bool = False  # set True in prod
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@meshtostep.pl"
    RATE_LIMIT_PER_MIN: int = 30  # auth attempts per IP per minute
    PASSWORD_RESET_HOURS: int = 2

    class Config:
        env_file = ".env"


settings = Settings()
