from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager
from app.core.config import settings 


# Создаем async engine
engine = create_async_engine(
  settings.DATABASE_URL,
  pool_pre_ping=True,
  pool_size=10,
  max_overflow=20,
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
  async with AsyncSession() as session:
    yield session 