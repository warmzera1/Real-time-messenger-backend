import pytest 
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.services.chat_service import ChatService
from app.models.chat import ChatRoom
from app.schemas.chat import ChatRoomCreate, ChatRoomBase
from app.schemas.user import UserResponse
from app.dependencies.auth import get_current_user 
from app.main import app


@pytest.mark.asyncio
async def test_create_chat_success(async_client, mocker, current_user):
    chat = ChatRoom(
      id=10, 
      name=None, 
      is_group=False, 
      created_at=datetime.utcnow(), 
      participants=[]
    )

    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.chat_service.ChatService.find_or_create_private_chat",
        new_callable=AsyncMock,
        return_value=chat
    )

    try: 
      response = await async_client.post(
          "/chats/",
          json={"second_user_id": 2},
          headers={"Authorization": "Bearer token"}
      )

      assert response.status_code == 200
    finally:
       app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_create_chat_user_not_found(async_client, mocker, current_user):

    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.chat_service.ChatService.find_or_create_private_chat",
        side_effect=ValueError("USER_NOT_FOUND")
    )

    try: 
      response = await async_client.post(
          "/chats/",
          json={"second_user_id": 999},
          headers={"Authorization": "Bearer token"}
      )

      assert response.status_code == 404
      assert response.json()["detail"] == "USER_NOT_FOUND"
    finally:
       app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_user_chats(async_client, mocker, current_user):
  mock_chat_ids = [1, 2]

  app.dependency_overrides[get_current_user] = lambda: current_user

  mock_service = mocker.patch(
    "app.services.chat_service.ChatService.get_user_chat_ids",
    new_callable=AsyncMock,
    return_value=mock_chat_ids
  )

  try:
    response = await async_client.get("/chats/")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert data[0] == {"id": 1}
    assert data[1] == {"id": 2}

    mock_service.assert_awaited_once_with(current_user.id, mocker.ANY)
  finally:
    app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_search_users_success(async_client, mocker, current_user):
  mock_users = [
    {
      "id": 1,
      "username": "test1",
      "email": "test1@mail.com",
      "is_active": True,
      "created_at": datetime.utcnow().isoformat()
    },
    {
      "id": 2,
      "username": "test2",
      "email": "test2@mail.com",
      "is_active": True,
      "created_at": datetime.utcnow().isoformat()
    }
  ]

  app.dependency_overrides[get_current_user] = lambda: current_user

  mock_service = mocker.patch(
    "app.services.chat_service.ChatService.search_users",
    new_callable=AsyncMock,
    return_value=mock_users
  )

  try:
    response = await async_client.get(
      "/chats/search",
      params={"q": "test"}
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert data[0]["username"] == "test1"
    assert data[1]["id"] == 2

    mock_service.assert_awaited_once_with(
      query="test",
      exclude_user_id=current_user.id,
      limit=20,
      db=mocker.ANY,
    )
  finally:
    app.dependency_overrides = {}




