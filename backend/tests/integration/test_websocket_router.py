from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient 

from app.main import app
 


@pytest.mark.asyncio 
async def test_websocket_auth_and_connect(mocker):
    client = TestClient(app)

    mock_connect = mocker.patch(
        "app.websocket.manager.websocket_manager.connection_manager.connect",
        return_value=1
    )

    mocker.patch(
        "app.websocket.manager.websocket_manager.message_handler.receive_loop",
        new_callable=AsyncMock
    )
    mocker.patch(
        "app.websocket.manager.websocket_manager.delivery_manager.send_pending_messages",
        new_callable=AsyncMock
    )

    with client.websocket_connect(
        "/ws",
        headers={"Authorization": "Bearer mock-token"}
    ) as websocket:
        assert mock_connect.called