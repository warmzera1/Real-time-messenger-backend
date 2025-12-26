from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker 
from app.core.config import settings 


# Создаем async engine
engine = create_async_engine(
  settings.DATABASE_URL,
  pool_pre_ping=True,
  pool_size=10,
  max_overflow=20,
  echo=settings.DEBUG,      # Вывод SQL-запросов в консоль
)

# Session для async
AsyncSessionLocal = sessionmaker(
  bind=engine,
  class_=AsyncSession,
  expire_on_commit=False,
  autoflush=False,
  autocommit=False,
)

# Контекстный менеджер для зависимостей
async def get_db() -> AsyncSession:
  async with AsyncSessionLocal() as session:
    try:
      yield session
    finally:
      await session.close()