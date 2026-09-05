"""Config via env vars."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/meshtostep.db"
    SECRET_KEY: str = "CHANGE-ME-in-production-use-openssl-rand-hex-32"
    FREE_CREDITS: int = 3
    MAX_FILE_MB: int = 50
    FREECAD_CMD: str = "/usr/bin/freecadcmd"  # Docker path
    DATA_DIR: str = "./data"
    CORS_ORIGINS: str = "*"
    APP_NAME: str = "MeshToStep"
    APP_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"


settings = Settings()
