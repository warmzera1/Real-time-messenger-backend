from unittest.mock import AsyncMock, patch
import pytest 

from app.models.user import User 
from app.dependencies.auth import get_current_user 
from app.main import app


@pytest.mark.asyncio 
async def test_register_success(async_client, mocker):
    mocker.patch(
        "app.routers.auth.AuthService.register",
        new_callable=AsyncMock,
        return_value={
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
        }
    )

    payload = {
        "email": "test@mail.com",
            "username": "testuser",
            "password": "password123"
        }

    response = await async_client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json() == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
    }


@pytest.mark.asyncio 
async def test_register_exists(async_client, mocker):
    mocker.patch(
        "app.routers.auth.AuthService.register",
        side_effect=ValueError("USER_EXISTS")
    )

    payload = {
        "username": "testuser",
        "email": "test@mail.com",
        "password": "password123"
    }

    response = await async_client.post(
        "/auth/register", 
        json=payload
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Пользователь с таким email или username уже зарегистрирован"
    )


@pytest.mark.asyncio
async def test_login_success(async_client, mocker):
    mocker.patch(
        "app.routers.auth.AuthService.login",
        new_callable=AsyncMock,
        return_value={
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer"
        }
    )

    payload = {
        "username": "testuser",
        "password": "password123"
    }

    response = await async_client.post(
        "/auth/login",
        json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "access-token"
    assert data["refresh_token"] == "refresh-token"
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid(async_client, mocker):
    mocker.patch(
        "app.routers.auth.AuthService.login",
        new_callable=AsyncMock,
        side_effect=[
            ValueError("NO_IDENTIFIER"),
            ValueError("INVALID_CREDENTIALS")
        ]
    )

    response1 = await async_client.post(
        "/auth/login",
        json={
            "username": "",
            "password": "password123"
        }
    )

    assert response1.status_code == 400

    response2 = await async_client.post(
        "/auth/login", 
        json = {
            "username": "wronguser",
            "password": "password123"
        }
    )

    assert response2.status_code == 401


@pytest.mark.asyncio 
async def test_refresh_success(async_client, mocker):
    mocker.patch(
        "app.routers.auth.AuthService.refresh_token",
    return_value={
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "token_type": "bearer"
        }
    )

    payload = {
        "refresh_token": "valid-refresh-token"
    }
 
    response = await async_client.post(
        "/auth/refresh",
        json=payload
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "side_effect, expected_status",
    [
        ("INVALID_REFRESH", 401),
        ("REFRESH_REVOKED", 401),
        ("USER_INACTIVE", 401),
    ]
)
async def test_refresh_invalid_token(async_client, mocker, side_effect, expected_status):
    mocker.patch(
        "app.routers.auth.AuthService.refresh_token",
        new_callable=AsyncMock,
        side_effect=ValueError(side_effect)
    )

    response1 = await async_client.post(
        "/auth/refresh",
        json={
        "refresh_token": "dummy-token"
        }
    )

    assert response1.status_code == expected_status


@pytest.mark.asyncio
async def test_logout_success(async_client, mocker):
    app.dependency_overrides[get_current_user] = lambda: User(id=1)

    mock_logout = mocker.patch(
        "app.routers.auth.AuthService.logout",
        new_callable=AsyncMock
    )

    try:
        response = await async_client.post(
            "/auth/logout",
            json={"refresh_token": "valid-refresh-token"},
            headers={"Authorization": "Bearer mock-token"}
        )

        assert response.status_code == 204
        mock_logout.assert_called_once_with(
            refresh_token="valid-refresh-token", 
            current_user=1
        )
    finally:
      app.dependency_overrides = {}

  
@pytest.mark.asyncio
async def test_logout_invalid_token(async_client, mocker):
    app.dependency_overrides[get_current_user] = lambda: User(id=1)

    mocker.patch(
        "app.routers.auth.AuthService.logout",
        side_effect=ValueError("INVALID_TOKEN") 
    )

    response = await async_client.post(
        "/auth/logout",
        json={"refresh_token": "bad_token"}
    )

    assert response.status_code == 401 

