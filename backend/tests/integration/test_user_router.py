import pytest 
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.models.user import User
from app.dependencies.auth import get_current_user 
from app.main import app

@pytest.mark.asyncio 
async def test_read_users_me(async_client): 
  user_data = User(
    id=1,
    username="testuser",
    email="test@mail.com",
    is_active=True,
    created_at=datetime.utcnow().isoformat()
  )

  app.dependency_overrides[get_current_user] = lambda: user_data

  try:
    response = await async_client.get("/users/me")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == user_data.id
    assert data["username"] == user_data.username 
    assert data["email"] == user_data.email
    assert data["is_active"] == user_data.is_active
    assert data["created_at"] == user_data.created_at
  finally:
    app.dependency_overrides = {}