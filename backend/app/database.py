from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager
from app.core.config import settings 

engine_kwargs = {
  "pool_pre_ping": True
}

if "sqlite" not in settings.DATABASE_URL:
  engine_kwargs.update({
    "pool_size": 5,
    "max_overflow": 10,
  })


# Создаем async engine
engine = create_async_engine(
  settings.DATABASE_URL,
  **engine_kwargs,
  # echo=settings.DEBUG,      # Вывод SQL-запросов в консоль
)

# Session для async
AsyncSessionLocal = async_sessionmaker(
  bind=engine,
  class_=AsyncSession,
  expire_on_commit=False,
  autoflush=False,
  autocommit=False,
)

# Для FastAPI Depends
async def get_db() -> AsyncSession:
  async with AsyncSessionLocal() as session:
    yield session


# Для WebSocket / background / services
@asynccontextmanager
async def get_db_session():
  async with AsyncSessionLocal() as session:
    yield session 