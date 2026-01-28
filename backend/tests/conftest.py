import pytest 

from sqlalchemy.ext.asyncio import (
  AsyncSession,
  create_async_engine,
  async_sessionmaker,
)


from app.models.base import Base 


@pytest.fixture(scope="session")
async def async_engine():
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    future=True,
    echo=False,
  )

  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all) 

  yield engine 

  await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
  async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
  )

  async with async_session_factory() as session:
    yield session 
    await session.rollback()