from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Local Work Marketplace API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "local_work_marketplace"

    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    CLERK_ISSUER: str = ""

    FIREBASE_CREDENTIALS_PATH: str = ""
    ENABLE_FIREBASE_STORAGE: bool = False
    FIREBASE_STORAGE_BUCKET: str = ""

    CORS_ORIGINS: str = "http://localhost:8081"

    RATE_LIMIT_AUTH_PER_HOUR: int = 100
    RATE_LIMIT_CONVERSATIONS_PER_DAY: int = 20
    MAX_ACTIVE_JOBS_PER_DAY: int = 3
    MAX_IMAGE_SIZE_MB: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
