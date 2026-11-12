"""Environment is read on each factory invocation; .env is not auto-loaded."""
import os
from datetime import timedelta
from pathlib import Path


class DevelopmentConfig:
    DEBUG = False
    TESTING = False
    SECRET_KEY = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_NAME = "honeyvault_auth"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_REFRESH_EACH_REQUEST = False
    MAX_CONTENT_LENGTH = 16 * 1024
    RATELIMIT_STORAGE_URI = "memory://"

    @staticmethod
    def environment():
        root = Path(__file__).resolve().parents[1]
        path = Path(os.environ.get("DATABASE_PATH", "instance/honeyvault.sqlite3"))
        if not path.is_absolute():
            path = root / path
        return {"SECRET_KEY": os.environ.get("SECRET_KEY") or None,
                "SESSION_COOKIE_SECURE": os.environ.get("HONEYVAULT_ENV", "production") != "development",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + path.resolve().as_posix()}


class TestingConfig(DevelopmentConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
