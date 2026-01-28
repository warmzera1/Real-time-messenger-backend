from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import UserCreate, LoginForm
from app.schemas.token import (
  TokenResponse, 
  RefreshTokenRequest, 
  LogoutRefreshTokenRequest
)
from app.services.auth_service import AuthService
from app.models.user import User 
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", 
    response_model=TokenResponse, 
    status_code=status.HTTP_201_CREATED
)
async def register(
  user_data: UserCreate, 
  db: AsyncSession = Depends(get_db)
):
  try:
    return await AuthService.register(user_data, db)
  except ValueError as e:
    if str(e) == "USER_EXISTS":
      raise HTTPException(
        status_code=400,
        detail="Пользователь с таким email или username уже зарегистрирован"
      )
    raise HTTPException(500, "Ошибка регистрации")


@router.post("/login", response_model=TokenResponse)
async def login(
  form: LoginForm, 
  db: AsyncSession = Depends(get_db)
):
  try:
    return await AuthService.login(form, db)
  except ValueError as e:
    if str(e) == "NO_IDENTIFIER":
      raise HTTPException(400, "Укажите username или email")
    if str(e) == "INVALID_CREDENTIALS":
      raise HTTPException(401, "Неверные учетные данные")
    raise HTTPException(500, "Ошибка авторизации")
  

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
  data: RefreshTokenRequest, 
  db: AsyncSession = Depends(get_db)
):
  try:
    return await AuthService.refresh_token(data, db)
  except ValueError as e:
    mapping = {
      "INVALID_REFRESH": 401,
      "REFRESH_REVOKED": 401,
      "USER_INACTIVE": 401,
    }
    status_code = mapping.get(str(e), 500)
    raise HTTPException(status_code, "Невалидный refresh токен")


@router.post("/logout", status_code=204)
async def logout(
  data: LogoutRefreshTokenRequest, 
  current_user: User = Depends(get_current_user)
):
  try:
    await AuthService.logout(
      refresh_token=data.refresh_token,
      current_user=current_user.id
    )
  except ValueError as e:
    mapping = {
      "INVALID_TOKEN": 401,
      "FORBIDDEN": 403,
      "ALREADY_REVOKED": 401,
    }
    raise HTTPException(
      status_code=mapping.get(str(e), 500),
      detail="Ошибка выхода"
    )


