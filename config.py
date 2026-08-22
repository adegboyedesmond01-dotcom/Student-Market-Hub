import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    # Supabase -> Project Settings -> Database -> Connection string -> URI
    # Put the real value in .env, never in this file.
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB per upload

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
