from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth 
from app.routers import users
from app.routers import chat
from app.routers import messages
# from app.routers import websocket 
from app.core.config import settings
from app.models.base import Base
from app.database import engine 
import asyncio


app = FastAPI(title="My Messenger")

# Создаем таблицы 
@app.on_event("startup")
async def create_tables():
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

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

@app.get("/")
async def root():
  return {"message": "Api ready"}