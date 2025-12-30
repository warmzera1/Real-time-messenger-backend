from fastapi import Depends, HTTPException, status 
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt 
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select
import json

from app.database import get_db 
from app.models.user import User 
from app.core.config import settings
from app.redis import redis_manager


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
CACHE_TTL = 60    # Секунд


async def get_current_user(
  token: str = Depends(oauth2_scheme), 
  db: AsyncSession = Depends(get_db)
) -> dict:
  """
  Dependency: Получает конкретного пользователя по JWT
  """

  try:
    # 1. Декодируем токен
    payload = jwt.decode(
      token,
      settings.SECRET_KEY,
      algorithms=[settings.ALGORITHM]
    )

    # 2. Извлекаем идентификатор пользователя из БД, закодированный в JWT-токене
    user_id: str | None = payload.get("sub")
    if user_id is None:
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Невалидный токен",
      )
  
  # 3. Если токен поврежден - ошибка
  except JWTError:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Невалидный токен",
    )
  
  cache_key = f"user:profile:{user_id}"
  
  # 4. Пытаемся взять данные из Redis
  try:
    cached_user = await redis_manager.get_cached_user_profile(int(user_id))
    if cached_user:
      return cached_user
    
  except Exception:
    cached_user = None 

  # 5. Если нет - идем в БД
  result = await db.execute(
    select(User).where(User.id == int(user_id))
  )
  user = result.scalar_one_or_none()

  # 6. Если пользователя нет - ошибка
  if not user:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Невалидный токен",
    )
  
  user_data = {
    "id": user.id,
    "username": user.username,
    "email": user.email,
  }

  # 7. Кладем в Redis с TTL
  try:
    await redis_manager.cache_user_profile(
      user.id,
      user_data,
      CACHE_TTL,
    )
  except Exception:
    pass      # Redis не должен ломать API
  
  # Возвращаем пользователя
  return user_data 