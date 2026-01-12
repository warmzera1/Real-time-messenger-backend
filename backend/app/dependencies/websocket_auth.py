import logging 
from typing import Optional 
from jose import JWTError, jwt 

from app.database import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession 
from app.models.user import User 
from app.core.config import settings 
from sqlalchemy import select 

logger = logging.getLogger(__name__)


async def get_current_user_ws(token: str) -> Optional[dict]:
  """
  Аутентификация для WebSocket
  Возвращает словарь с базовыми данными пользователя
  """

  try:
    # 1. Декодируем токен
    payload = jwt.decode(
      token,
      settings.SECRET_KEY,
      algorithms=[settings.ALGORITHM]
    )
    user_id = payload.get("sub")

    if not user_id:
      logger.warning(f"В токене отсутствует user_id")
      return None 
    
    # 2. Используем существующую сессию или создаем новую
    async with AsyncSessionLocal() as db:
      # 3. Ищем пользователя
      result = await db.execute(
        select(User)
        .where(User.id == int(user_id))
      )
      user = result.scalar_one_or_none()

      if not user:
        logger.warning(f"Пользователь {user_id} не найден")
        return None 
      
      if not user.is_active:
        logger.warning(f"Пользователь {user_id} неактивен")

      # 4. Возвращаем минимальные данные
      return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
      }
    
  except JWTError as e:
    logger.warning(f"JWT ошибка: {e}")
    return None 
  except Exception as e:
    logger.error(f"WebSocket auth ошибка: {e}")
    return None 