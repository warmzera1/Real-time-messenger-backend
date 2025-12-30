from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import asyncio
import logging

from app.routers import auth 
from app.routers import users
from app.routers import chat
from app.routers import messages
from app.routers import websocket 
from app.core.config import settings
from app.models.base import Base
from app.database import engine 
from app.redis.manager import redis_manager


logger = logging.getLogger(__name__)


app = FastAPI(title="My Messenger")

# Создаем таблицы 
@app.on_event("startup")
async def create_tables():
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
    
@app.on_event("startup")
async def startup_event():
  # Проверяем Redis
  try:
    if await redis_manager.connect():
      logger.info(f"[startup_event] Redis подключен успешно")
    else:
      logger.warning(f"[startup_event] Redis недоступен, работаем без кэша")

  except Exception as e:
    logger.error(f"[startup_event] Ошибка подключения к Redis: {e}")


# CORS
app.add_middleware(
  CORSMiddleware,
  allow_origins=settings.ALLOWED_ORIGINS,   # Список разрешенных доментов для запросов
  allow_credentials=True,                   # Разрешает куки/авторизацию 
  allow_methods=["*"],                      # Все HTTP-методы
  allow_headers=["*"],                      # Все заголовки
)

# Роутеры
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chat.router)
app.include_router(messages.router)
app.include_router(websocket.router)

@app.get("/")
async def root():
  return {"message": "Api ready"}

import logging
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket.log')
    ]
)