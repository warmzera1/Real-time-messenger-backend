import pytest 

from sqlalchemy import insert, select 

from app.models.chat import ChatRoom
from app.models.participant import participants
from app.models.user import User 
from app.services.chat_service import ChatService
from unittest.mock import AsyncMock, patch 


@pytest.mark.asyncio
async def test_get_chat_members(async_session):
  user_ids_to_insert = [1, 2]
  chat_id = 1

  for user_id in user_ids_to_insert:
    await async_session.execute(
      insert(participants).values(chat_id=chat_id, user_id=user_id),
    )
  await async_session.commit() 

  member_ids = await ChatService.get_chat_members(
    chat_id=chat_id,
    db=async_session
  )

  assert set(member_ids) == {1, 2}


@pytest.mark.asyncio
async def test_get_user_chat_ids(async_session):
  user_id = 1
  chat_ids_to_insert = [1, 2]
  
  for chat_id in chat_ids_to_insert:
    await async_session.execute(
      insert(participants).values(chat_id=chat_id, user_id=user_id)
    )
  await async_session.commit()

  chat_ids = await ChatService.get_user_chat_ids(
    user_id=user_id,
    db=async_session
  )

  assert set(chat_ids) == {1,2}


@pytest.mark.asyncio
async def test_find_or_create_private_chat_existing(async_session):
  chat = ChatRoom(is_group=False)
  async_session.add(chat)
  await async_session.flush()
  await async_session.execute(
    insert(participants).values([
      {"chat_id": 1, "user_id": 1},
      {"chat_id": 1, "user_id": 2},
    ])
  )

  await async_session.commit()

  result = await ChatService.find_or_create_private_chat(1, 2, async_session)
  assert result.id == chat.id


@pytest.mark.asyncio
async def test_find_or_create_private_chat_create_new(async_session):
  with patch(
    "app.services.chat_service.redis_manager.add_user_to_chat",
    new_callable=AsyncMock
  ) as mock_redis:
  
    chat = await ChatService.find_or_create_private_chat(3, 4, async_session)
    assert chat is not None
    assert chat.is_group is False 

    result = await async_session.execute(
      select(participants).where(
        participants.c.chat_id == chat.id
      )
    )
    users = result.scalars().all()
    assert set(users) == {3, 4}

    mock_redis.assert_any_await(3, chat.id)
    mock_redis.assert_any_await(4, chat.id)


@pytest.mark.asyncio
async def test__find_private_chat(async_session):
  chat1 = ChatRoom(is_group=False)
  chat2 = ChatRoom(is_group=True)
  async_session.add_all([chat1, chat2])
  await async_session.flush()
  await async_session.execute(
    insert(participants).values([
      {"chat_id": chat1.id, "user_id": 1},
      {"chat_id": chat1.id, "user_id": 2},
      {"chat_id": chat2.id, "user_id": 1},
      {"chat_id": chat2.id, "user_id": 2},
    ])
  )
  await async_session.commit()

  result = await ChatService._find_private_chat(1, 2, async_session)
  assert result.id == chat1.id 


@pytest.mark.asyncio
async def test__create_private_chat(async_session):
  chat = await ChatService._create_private_chat(5, 6, async_session)
  assert chat is not None 
  assert chat.is_group is False 

  result = await async_session.execute(
    select(participants.c.user_id).where(
      participants.c.chat_id == chat.id
    )
  )
  users = result.scalars().all() 
  assert set(users) == {5, 6}


@pytest.mark.asyncio
async def test_search_users(async_session):
  users = [
    User(id=1, username="alice", email="b@gmail.com", hashed_password="12345", is_active=True),
    User(id=2, username="bob", email="a@gmail.com", hashed_password="12345", is_active=True),
    User(id=3, username="alicia", email="c@gmail.com", hashed_password="12345", is_active=False),
  ]
  async_session.add_all(users)
  await async_session.commit()

  result = await ChatService.search_users(
    "ali", exclude_user_id=2, limit=10, db=async_session,
  )
  usernames = [u.username for u in result]

  assert "alice" in usernames 
  assert "alicia" not in usernames 
  assert "bob" not in usernames 
  assert all(u.is_active for u in result)

  result_limited = await ChatService.search_users(
    "a", exclude_user_id=99, limit=1, db=async_session
  )
  assert len(result_limited) == 1
  

