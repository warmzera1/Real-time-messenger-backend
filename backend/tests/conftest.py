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
  async def _get_db_override():
    yield async_session 

  app.dependency_overrides[get_db] = _get_db_override 
  yield 
  app.dependency_overrides.clear()


@pytest.fixture 
async def async_client():
  async with AsyncClient(
    transport=ASGITransport(app=app),
    base_url="http://test", 
    proxy=None
    ) as client:
      yield client 


@pytest.fixture
async def test_user(async_session):
  user = User(
    username="testuser",
    email="test@mail.com",
    hashed_password="password123"
  )
  async_session.add(user)
  await async_session.commit()
  await async_session.refresh(user)

  return user



@pytest.fixture
async def auth_token(async_client, test_user):

  response = await async_client.post(
    "/auth/login",
    json={
      "username": test_user.username,
      "password": "password123",
    }
  )

  assert response.status_code == 200 
  
  data = response.json()
  access_token = data.get["access_token"]
  return access_token


@pytest.fixture
def auth_headers(auth_token):
  return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def logout_payload():
    return {
        "refresh_token": "test-refresh-token-123"
    }

