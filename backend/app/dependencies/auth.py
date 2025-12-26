from fastapi import Depends, HTTPException, status 
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt 
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select

from app.database import get_db 
from app.models.user import User 
from app.core.config import settings 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
  token: str = Depends(oauth2_scheme), 
  db: AsyncSession = Depends(get_db)
) -> User:
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

  # 4. Поиск пользователя в БД 
  result = await db.execute(select(User).where(User.id == int(user_id)))
  user = result.scalar_one_or_none()

  # 5. Если пользователя нет - ошибка
  if not user:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Невалидный токен",
    )
  
  # Возвращаем пользователя
  return user 