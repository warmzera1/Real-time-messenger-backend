from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import asyncio
import sys

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


# ======== LIFESPAN ========
@asynccontextmanager
async def lifespan(app: FastAPI):
  """
  Управление жизненным циклом приложения
  """
  
  # Startup
  logger.info("Запуск приложения...")

  # 1. Создаем таблицы в БД
  try:
    async with engine.begin() as conn:
      await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы БД созданы/проверены")

  except Exception as e:
    logger.error(f"Ошибка создания таблиц БД: {e}")
    raise

  # 2. Подключение Redis
  try:
    if await redis_manager.connect():
      logger.info(f"[connect] Redis подключен")
    else:
      logger.warning(f"[connect] Redis недоступен, работаем без кэша")
  
  except Exception as e:
    logger.warning(f"[connect] Ошибка Redis (продолжаем без кэша): {e}")

  logger.info(f"Приложение запущено")

  yield     # Работает приложение


# ======== APP INIT ========
app = FastAPI(
  title="My Messenger",
  version="1.0.0",
  lifespan=lifespan,
)


# ======== CORS ========
app.add_middleware(
  CORSMiddleware,
  allow_origins=settings.ALLOWED_ORIGINS,   # Список разрешенных доментов для запросов
  allow_credentials=True,                   # Разрешает куки/авторизацию 
  allow_methods=["*"],                      # Все HTTP-методы
  allow_headers=["*"],                      # Все заголовки
)


# ======== ROUTERS ========
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chat.router)
app.include_router(messages.router)
app.include_router(websocket.router)


# ======== HEALTH CHECK ========
@app.get("/health")
async def health_check():
  """Проверка состояния сервиса"""

  return {
    "status": "healthy",
    "service": "messenger",
    "timestamp": datetime.now().isoformat()
  }


@app.get("/")
async def root():
  return {
    "message": "My messenger API",
    "docs": "/docs",
    "redoc": "/redoc",
  }


# ======== SETTINGS LOGGER ========
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket.log')
    ]
)