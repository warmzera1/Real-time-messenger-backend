from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import asyncio

from app.routers import auth, users, chat, messages, websocket
from app.core.config import settings
from app.models.base import Base
from app.database import engine 
from app.redis.manager import redis_manager
from app.websocket.manager import websocket_manager

logger = logging.getLogger(__name__)


# ======== LIFESPAN ========
@asynccontextmanager
async def lifespan(app: FastAPI):
  """
  Управление жизненным циклом приложения
  """
  
  # STARTUP
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
    connected = await redis_manager.connect()
    if connected:
      logger.info("Redis успешно подключился")

      # Устанавливаем связь между менеджерами
      redis_manager.set_websocket_manager(websocket_manager)
      logger.info("WebSocketManager связан с RedisManager")

      # Запускаем Redis слушатель
      await redis_manager.start_listening()
      logger.info("Redis Pub/Sub listener запущен")
    else:
      logger.warning("Redis недоступен, запуск без кэша")
  
  except Exception as e:
    logger.warning(f"Redis ошибка подключения (продолжать без): {e}")


  logger.info("Приложение запущено успешно")

  yield # Приложение работает

  # SHUTDOWN
  logger.info("Завершение работы приложения...")

  try:
    await redis_manager.close()
    logger.info("Redis соединение закрыто")
  except Exception as e:
    logger.error(f"Ошибка закрытия Redis: {e}")

  logger.info("Приложение остановлено")


# ======== APP INIT ========
app = FastAPI(
  title="Messenger API",
  description="Приложение для обмена сообщениями в режиме реального времени",
  version="1.0.0",
  lifespan=lifespan,
  docs_url="/docs" if settings.DEBUG else None,
  redoc_url="/redoc" if settings.DEBUG else None,
)


# ======== CORS ========
app.add_middleware(
  CORSMiddleware,
  allow_origins=settings.ALLOWED_ORIGINS,   # Список разрешенных доменов для запросов
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
  import datetime 

  redis_status = "неизвестный"
  try:
    redis_status = "подключен" if await redis_manager.connect() else "отключен"
  except:
    redis_status = "ошибка"

  return {
    "status": "healthy",
    "service": "messenger",
    "timestamp": datetime.datetime.now().isoformat(),
    "redis": redis_status,
    "websocket_connections": len(websocket_manager.active_connections),
    "version": "1.0.0"
  }


@app.get("/")
async def root():
  return {
    "message": "Messenger API",
    "docs": "/docs",
    "health": "/health",
    "websocket": "/ws",
  }


# ======== SETTINGS LOGGER ========
# if __name__ == "__main__":
import sys
import uvicorn

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('websocket.log')
    ]
)

# uvicorn.run(
#    "app.main:app",
#    host="0.0.0.0",
#    port=8000,
#    reload=settings.DEBUG,
#    log_level="debug" if settings.DEBUG else "info",
# )