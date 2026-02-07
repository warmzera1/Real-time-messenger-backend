from typing import List

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Все настройки приложения
    """

    PROJECT_NAME: str = "MyMessenger"
    DEBUG: bool = False 

    # Безопасность
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7              

    # Подключения (валидируют формат строки)
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn

    # CORS - какие фронтенды могут подключаться
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",          
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

if __name__ == "__main__":
    print(settings.model_dump())