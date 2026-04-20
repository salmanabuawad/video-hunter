import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://video_hunter:video_hunter@127.0.0.1:5432/video_hunter",
)

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./data/downloads")
THUMB_DIR = os.getenv("THUMB_DIR", "./data/thumbs")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-prod")
JWT_EXP_HOURS = int(os.getenv("JWT_EXP_HOURS", "12"))
COOKIE_NAME = "vh_session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() in ("1", "true", "yes")

ADMIN_DEFAULT_USERNAME = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8030"))

_cors = os.getenv("CORS_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174")
CORS_ORIGINS = [o.strip() for o in _cors.split(",") if o.strip()]
