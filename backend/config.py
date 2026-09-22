import os
import secrets
import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger("config")


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./foodwaste.db"
    SECRET_KEY: str = None  # type: ignore
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # CORS: comma separated list of allowed origins.
    # Always includes the Vite dev origin so the frontend keeps working.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Job scheduling times (24h). Used by scheduler.py.
    DAILY_JOB_TIME: str = "02:00"
    WEEKLY_JOB_DAY: str = "mon"
    WEEKLY_JOB_TIME: str = "03:00"

    # Risk score thresholds (override via RISK_THRESHOLDS env when needed).
    RISK_THRESHOLDS: str = "35,60,80"  # low|moderate = 0-35, moderate|high = 36-60, high|critical = 61-80, critical = 81-100

    class Config:
        env_file = ".env"

    def resolved_secret_key(self) -> str:
        """Return the configured secret or an ephemeral random one.

        Never falls back to a hard-coded value. An ephemeral key means tokens
        are invalidated on restart, which is safer than shipping a known key.
        """
        if self.SECRET_KEY and self.SECRET_KEY != "change-me":
            return self.SECRET_KEY
        generated = secrets.token_urlsafe(48)
        logger.warning(
            "SECRET_KEY not set in environment. Generated an ephemeral random key "
            "(sessions will be invalidated on restart). Set SECRET_KEY in backend/.env for stable tokens."
        )
        return generated

    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()