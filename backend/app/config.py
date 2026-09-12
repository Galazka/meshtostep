"""Config via env vars."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/meshtostep.db"
    SECRET_KEY: str
    MAX_FILE_MB: int = 200
    FREECAD_CMD: str = "/usr/bin/freecadcmd"  # Docker path
    DATA_DIR: str = "./data"
    CORS_ORIGINS: str = "*"
    APP_NAME: str = "3dfile.link"
    APP_URL: str = "https://3dfile.link"
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
