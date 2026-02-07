import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware

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
    
    logger.info("Запуск приложения...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Таблицы БД созданы/проверены")

    except Exception as e:
        logger.error(f"Ошибка создания таблиц БД: {e}")
        raise

    try:
        await redis_manager.redis.ping()
        logger.info(f"Redis подключен")
    except Exception as e:
        logger.warning(f"Redis ошибка подключения: {e}")

    try:
        asyncio.create_task(
            redis_manager.subscribe_to_chats(
            lambda chat_id, msg: websocket_manager.delivery_manager.broadcast_to_chat(chat_id, msg)
            )
        )
        logger.info(f"Redis Pub/Sub слушатель запущен")
    except Exception as e:
        logger.error(f"Ошибка запуска Pub/Sub: {e}")

    logger.info("Приложение запущено успешно")

    yield 


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

    redis_status = "отключен"
    try:
        await redis_manager.redis.ping()
        redis_status = "подключен"
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

