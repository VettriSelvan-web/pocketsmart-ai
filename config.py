"""Central configuration loaded from environment variables / .env file."""
import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("pocketsmart")


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class Settings:
    APP_NAME = "PocketSmart AI"

    GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if GEMINI_API_KEY.startswith("your_"):  # placeholder copied from .env.example
        GEMINI_API_KEY = ""
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
    GEMINI_FALLBACK_MODELS = _split(
        os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite,gemini-3-flash-preview")
    )

    SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
    if not SECRET_KEY or SECRET_KEY.startswith("change-me"):
        SECRET_KEY = secrets.token_hex(32)
        logger.warning(
            "SECRET_KEY not set in .env - using a temporary key. "
            "Users will be logged out whenever the server restarts."
        )
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    COOKIE_NAME = "access_token"

    CORS_ORIGINS = _split(os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"))

    _db = Path(os.getenv("DB_PATH", "data/pocketsmart.db"))
    DB_PATH = _db if _db.is_absolute() else BASE_DIR / _db

    UPLOAD_DIR = BASE_DIR / "static" / "uploads"
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))


settings = Settings()
