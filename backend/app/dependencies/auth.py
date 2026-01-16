from fastapi import Depends, HTTPException, status 
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt 
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select 
from typing import Optional 

from app.database import get_db 
from app.models.user import User 
from app.core.config import settings 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
  """
  Dependency для HTTP эндпоинтов
  Возвращает объект User из БД
  """

  credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось проверить учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
  )

  try:
    # Декодируем токен
    payload = jwt.decode(
      token, 
      settings.SECRET_KEY,
      algorithms=[settings.ALGORITHM],
    )
    if payload.get("type") != "access":
      raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
      raise credentials_exception
    
  except JWTError:
    raise credentials_exception
  
  # Получаем пользователя из БД
  result = await db.execute(
    select(User).where(User.id == int(user_id))
  )
  user = result.scalar_one_or_none()

  if user is None or not user.is_active:
    raise credentials_exception
  
  return user 


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
  """
  Дополнительная проверка на активность пользователя
  """

  if not current_user.is_active:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Пользователь неактивен",
    )
  
  return current_user