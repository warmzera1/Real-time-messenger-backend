from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
  """
  Все настройки приложения
  """

  # Основные
  PROJECT_NAME: str = "MyMessenger"
  DEBUG: bool = True 

  # Безопастность 
  SECRET_KEY: str 
  ALGORITHM: str = "HS256"
  ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7    # 7 дней

  # База данных
  DATABASE_URL: str

  # CORS - какие фронтенды могут подключаться
  ALLOWED_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
  ]

  model_config = SettingsConfigDict(
    env_file=".env",          # Путь до .env
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
  )


# Экземляр настроек
settings = Settings()

if __name__ == "__main__":
    print(settings.model_dump())