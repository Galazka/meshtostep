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
    DEBUG: bool = False  # True only for local dev — enables reset-link stdout fallback
    print_margin_percent: float = 68.0  # Tom's markup on print cost
    ADMIN_EMAIL_PRINTER: str = ""  # Tom's email for order notifications
    # —— Multi-currency (hardcoded ECB rates, no API key required) ——
    currency_rate_usd: float = 4.20  # 1 USD = 4.20 PLN
    currency_rate_eur: float = 4.55  # 1 EUR = 4.55 PLN

    # --- Firma / NIP (B2B) ---
    # Sprzedaz jako osoba fizyczna (dzialalnosc nierejestrowana) => brak faktur VAT / NIP.
    # Wlaczenie: ustaw FIRM_ORDERS_ENABLED=true w env (Railway) + pokaz pola NIP w /zamow.
    # Frontend czyta to przez GET /api/config/features.
    FIRM_ORDERS_ENABLED: bool = False


    # --- Stripe ---
    STRIPE_SECRET_KEY: str = ""   # sk_...; empty = BLIK fallback
    STRIPE_WEBHOOK_SECRET: str = ""   # whsec_...
    STRIPE_PUBLIC_KEY: str = ""   # pk_...

    # --- InPost ShipX (wysylka paczkomatami) ---
    # Puste => admin widzi link-zastepczy (otwarcie w apce InPost z prefillem),
    # po zal.ozeniu dzialalnosci Tom podaje klucz organizacji (Railway env) i
    # automatyczna etykieta/QR startuje samoczynnie. Kierowanie na hit zawsze wraca.
    INPOST_API_KEY: str = ""          # sk_x lub token organizacji (panel InPost -> Organizacja -> API)
    INPOST_SENDER_ORG: str = "3dfile.link"      # nazwa organizacji/nadawcy widoczna na paczce
    INPOST_SENDER_STREET: str = "Orfeusza 44"   # Gdańsk Osowa (punkt nadania Tom wozu)
    INPOST_SENDER_CITY: str = "Gdańsk"
    INPOST_SENDER_POSTAL: str = "80-299"
    INPOST_SENDER_EMAIL: str = "hello@3dfile.link"
    INPOST_SENDER_PHONE: str = "+48 790 824 762"
    INPOST_SENDER_COUNTRY: str = "PL"

    class Config:
        env_file = ".env"


settings = Settings()
