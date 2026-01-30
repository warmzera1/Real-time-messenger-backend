import pytest 
from unittest.mock import AsyncMock, patch 

from app.services.auth_service import AuthService
from app.models.user import User 
from app.schemas.user import UserCreate, LoginForm

@pytest.mark.asyncio
async def test_register_success(async_session, mocker):
  user_data = UserCreate(
    username="testuser",
    email="test@mail.com",
    password="password123",
  )

  mocker.patch(
    "app.services.auth_service.create_access_token",
    return_value="access-token",
  )
  mocker.patch(
    "app.services.auth_service.create_refresh_token",
    return_value=("refresh-token", "jti")
  )
  redis_mock = mocker.patch(
    "app.services.auth_service.redis_manager.add_refresh_token",
    new_callable=AsyncMock,
  )

  result = await AuthService.register(user_data, async_session)

  assert result.access_token == "access-token"
  assert result.refresh_token == "refresh-token"
  redis_mock.assert_awaited_once()


@pytest.mark.asyncio 
async def test_register_exists(async_session):
  user = User(
    username="testuser",
    email="test@mail.com",
    hashed_password="hash",
  )
  async_session.add(user)
  await async_session.commit()

  user_data = UserCreate(
    username="testuser",
    email="test@mail.com",
    password="password123"
  )

  with pytest.raises(ValueError, match="USER_EXISTS"):
    await AuthService.register(user_data, async_session)


@pytest.mark.asyncio 
async def test_login_success(async_session, mocker):
  user = User(
    username="testuser",
    email="testemail@mail.com",
    hashed_password="hashed",
  )
  async_session.add(user)
  await async_session.commit()

  mocker.patch(
    "app.services.auth_service.verify_password",
    return_value=True
  )
  mocker.patch(
    "app.services.auth_service.create_access_token",
    return_value="access-token"
  )
  mocker.patch(
    "app.services.auth_service.create_refresh_token",
    return_value=("refresh-token", "jti")
  )
  mocker.patch(
    "app.services.auth_service.redis_manager.add_refresh_token",
    new_callable=AsyncMock
  )

  form = LoginForm(username="testuser", password="password")

  result = await AuthService.login(form, async_session)
  
  assert result.access_token == "access-token"


@pytest.mark.asyncio 
async def test_login_invalid_credentials(async_session, mocker):
  user = User(
    username="testuser",
    email="test@mail.com",
    hashed_password="hashed",
  )
  async_session.add(user)
  await async_session.commit() 

  mocker.patch(
    "app.services.auth_service.verify_password",
    return_value=False
  )

  form = LoginForm(username="testuser", password="wrong")

  with pytest.raises(ValueError, match="INVALID_CREDENTIALS"):
    await AuthService.login(form, async_session)


@pytest.mark.asyncio 
async def test_refresh_token_success(async_session, mocker):
  user = User(
    username="testuser",
    email="test@mail.com",
    hashed_password="hashed"
  )
  async_session.add(user)
  await async_session.commit() 

  mocker.patch(
    "app.services.auth_service.jwt.decode",
    return_value={"sub": str(user.id), "jti": "jti", "type": "refresh"}
  )
  mocker.patch(
    "app.services.auth_service.redis_manager.is_refresh_token_valid",
    new_callable=AsyncMock,
    return_value=True
  )
  mocker.patch(
    "app.services.auth_service.redis_manager.revoke_refresh_token",
    new_callable=AsyncMock
  )
  mocker.patch(
    "app.services.auth_service.create_access_token",
    return_value="new-access"
  )
  mocker.patch(
    "app.services.auth_service.create_refresh_token",
    return_value=("new-refresh", "new-jti")
  )
  mocker.patch(
    "app.services.auth_service.redis_manager.add_refresh_token",
    new_callable=AsyncMock
  )

  result = await AuthService.refresh_token(
    data=type("obj", (), {"refresh_token": "token"})(),
    db=async_session,
  )

  assert result.access_token == "new-access"


@pytest.mark.asyncio 
async def test_logout_success(mocker):
  mocker.patch(
    "app.services.auth_service.jwt.decode",
    return_value={"sub": "1", "jti": "jti", "type": "refresh"}
  )
  mocker.patch(
    "app.services.auth_service.redis_manager.is_refresh_token_valid",
    new_callable=AsyncMock,
    return_value=True
  )
  revoke = mocker.patch(
    "app.services.auth_service.redis_manager.revoke_refresh_token",
    new_callable=AsyncMock
  )

  await AuthService.logout("token", current_user_id=1)

  revoke.assert_awaited_once()