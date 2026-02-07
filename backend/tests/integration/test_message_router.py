from datetime import datetime
from unittest.mock import AsyncMock, patch
import pytest 

from app.dependencies.auth import get_current_user 
from app.main import app


@pytest.mark.asyncio 
async def test_send_message_success(async_client, mocker, current_user):
    mock_message = {
        "id": 100,
        "chat_id": 1,
        "sender_id": current_user.id,
        "content": "test",
        "created_at": datetime.utcnow().isoformat()
    }

    app.dependency_overrides[get_current_user] = lambda: current_user

    mock_service = mocker.patch(
        "app.services.message_service.MessageService.send_message",
        new_callable=AsyncMock,
        return_value=mock_message
    )

    try:
        response = await async_client.post(
        "/messages/",
        json={
            "chat_id": 1,
            "content": "test"
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert data["content"] == "test"
        assert data["sender_id"] == current_user.id 

        mock_service.assert_awaited_once_with(
            chat_id=1,
            sender_id=current_user.id,
            content="test",
            db=mocker.ANY
        )
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_send_message_failed(async_client, mocker, current_user):

    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.message_service.MessageService.send_message",
        side_effect=ValueError("FORBIDDEN")
    )

    try:
        response = await async_client.post(
        "/messages/",
        json={
            "chat_id": 999,
            "content": "test"
            }
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "FORBIDDEN"

    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_send_message_create_failed(async_client, mocker, current_user):

    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.message_service.MessageService.send_message",
        side_effect=ValueError("MESSAGE_CREATE_FAILED")
    )

    try:
        response = await async_client.post(
        "/messages/",
        json={
            "chat_id": 1,
            "content": "test message",
            }
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "MESSAGE_CREATE_FAILED"

    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_messages_success(async_client, mocker, current_user):
    mock_messages = [
        {
            "id": 1,
            "chat_id": 1,
            "sender_id": current_user.id,
            "content": "test",
            "created_at": datetime.utcnow().isoformat(),
            "delivered_at": None,
            "read_at": None,
            "is_deleted": False
        },
        {
            "id": 2,
            "chat_id": 1,
            "sender_id": 2,
            "content": "new message",
            "created_at": datetime.utcnow().isoformat(),
            "delivered_at": None,
            "read_at": None,
            "is_deleted": False
        },
    ]

    app.dependency_overrides[get_current_user] = lambda: current_user

    mock_service = mocker.patch(
        "app.services.message_service.MessageService.get_chat_messages",
        new_callable=AsyncMock,
        return_value=mock_messages
    )

    try:
        response = await async_client.get(
        "/messages/",
        params={"chat_id": 1}
        )

        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["content"] == "new message"

        mock_service.assert_awaited_once_with(
        chat_id=1,
        user_id=current_user.id,
        limit=50,
        offset=0,
        db=mocker.ANY
        )
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_get_messages_failed(async_client, mocker, current_user):

    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.message_service.MessageService.get_chat_messages",
        side_effect=ValueError("FORBIDDEN")
    )

    try:
        response = await async_client.get(
        "/messages/",
        params={"chat_id": 999}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Вы не являетесь участником чата"

    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_message_success(async_client, mocker, current_user):

    app.dependency_overrides[get_current_user] = lambda: current_user

    mock_service = mocker.patch(
        "app.services.message_service.MessageService.delete_message",
        new_callable=AsyncMock,
        return_value=None
    )

    try:
        message_id = 1
        response = await async_client.delete(
            f"/messages/{message_id}/delete",
        )

        assert response.status_code == 204

        mock_service.assert_awaited_once_with(
            message_id=1,
            user_id=current_user.id,
            db=mocker.ANY
        )
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_delete_message_not_found(async_client, mocker, current_user):

    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.message_service.MessageService.delete_message",
        side_effect=ValueError("MESSAGE_NOT_FOUND")
    )

    try:
        message_id = 1
        response = await async_client.delete(
            f"/messages/{message_id}/delete"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Сообщение не найдено"

    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_delete_message_forbidden(async_client, mocker, current_user):

    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.message_service.MessageService.delete_message",
        side_effect=ValueError("FORBIDDEN")
    )

    try:
        response = await async_client.delete(
            f"/messages/5/delete",
        )   

        assert response.status_code == 403
        assert response.json()["detail"] == "Сообщение не принадлежит Вам"

    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_edit_message_success(async_client, mocker, current_user):
    app.dependency_overrides[get_current_user] = lambda: current_user

    mock_service = mocker.patch(
        "app.services.message_service.MessageService.edit_message",
        new_callable=AsyncMock,
        return_value=True
    )

    try:
        message_id = 1
        response = await async_client.patch(
        f"/messages/{message_id}/edit",
        json={"content": "test"}
        )

        assert response.status_code == 200

        mock_service.assert_awaited_once_with(
            message_id=1,
            user_id=current_user.id,
            new_content="test",
            db=mocker.ANY
        )
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_edit_message_not_found(async_client, mocker, current_user):
    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.message_service.MessageService.edit_message",
        side_effect=ValueError("MESSAGE_NOT_FOUND")
    )

    try:
        message_id = 555
        response = await async_client.patch(
        f"/messages/{message_id}/edit",
        json={"content": "test"}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Сообщение не найдено"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio 
async def test_edit_message_forbidden(async_client, mocker, current_user):
    app.dependency_overrides[get_current_user] = lambda: current_user

    mocker.patch(
        "app.services.message_service.MessageService.edit_message",
        side_effect=ValueError("FORBIDDEN")
    )

    try:
        message_id = 555
        response = await async_client.patch(
        f"/messages/{message_id}/edit",
        json={"content": "test"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Сообщение не принадлежит Вам"
    finally:
        app.dependency_overrides = {}










