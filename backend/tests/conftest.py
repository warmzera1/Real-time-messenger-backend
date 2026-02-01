import pytest 

from httpx import AsyncClient 
from httpx._transports.asgi import ASGITransport
from sqlalchemy.ext.asyncio import (
  AsyncSession,
  create_async_engine,
  async_sessionmaker
)

from app.main import app 
from app.database import get_db 
from app.models.base import Base 
from app.models.user import User 
from app.schemas.user import UserCreate
from app.core.security import create_access_token


@pytest.fixture()
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
  session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
  )

  async with session_factory() as session:
    yield session 
    await session.rollback()


@pytest.fixture(autouse=True)
def override_get_db(async_session):
  app.dependency_overrides[get_db] = lambda: async_session
  yield 
  app.dependency_overrides.pop(get_db, None)


@pytest.fixture 
async def async_client():
  async with AsyncClient(
    transport=ASGITransport(app=app),
    base_url="http://test", 
    proxy=None
    ) as client:
      yield client 


@pytest.fixture
def current_user():
    return User(id=1, username="testuser", email="test@test.com")


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


