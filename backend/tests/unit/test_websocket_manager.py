import pytest 
from unittest.mock import AsyncMock, patch

from app.websocket.manager import DeliveryManager
from app.main import app
from fastapi.testclient import TestClient 


@pytest.mark.asyncio 
async def test_send_pending_messages(mocker):
  mock_ws = mocker.AsyncMock()
  mock_messages = [
    {
      "id": 1,
      "content": "hello"
    },
    {
      "id": 2,
      "content": "world",
    }
  ]

  mocker.patch(
    "app.redis.manager.redis_manager.get_and_remove_offline_messages",
    new_callable=AsyncMock,
    return_value=mock_messages,
  )

  mock_mark = mocker.patch(
    "app.services.message_service.MessageService.mark_delivered",
    new_callable=AsyncMock,
  )

  mock_db = mocker.AsyncMock()
  mocker.patch(
    "app.websocket.manager.get_db_session",
    return_value=mocker.MagicMock(__aenter__=AsyncMock(return_value=mock_db))
  )

  mock_conn_manager = mocker.MagicMock()

  manager = DeliveryManager(connection_manager=mock_conn_manager)
  await manager.send_pending_messages(user_id=1, ws=mock_ws)

  assert mock_ws.send_json.call_count == 2
  assert mock_mark.call_count == 2
  mock_mark.assert_awaited_with(message_id=2, user_id=1, db=mock_db)