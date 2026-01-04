from typing import List, Optional 
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select, desc 
from sqlalchemy.orm import selectionload 
import logging 

from app.models.chat import ChatRoom
from app.models.user import User 
from app.database import get_db 


logger = logging.getLogger(__name__)


class ChatService:
  """
  Сервис для работы с чатами
  Переиспользует логику из роутеров
  """

  @staticmethod
  async def get_user_chats(user_id: int, db: Optional[AsyncSession] = None) -> List[ChatRoom]:
    """
    Получение всех чатов пользователя

    Args:
      user_id: ID пользователя
      db: Необязательная сессия БД. Если None - создаст новую

    Returns:
      Список объектов ChatRoom
    """

    close_db = False
    if db is None:
      db = await get_db().__anext__()
      close_db = True 

    try:
      stmt = (
        select(ChatRoom)
        .join(ChatRoom.participants)
        .where(ChatRoom.participants.any(User.id == user_id))
        .options(selectionload(ChatRoom.participants))
        .order_by(desc(ChatRoom.created_at))
      )

      result = await db.execute(stmt)
      chats = result.scalars().all()

      logger.info(f"[ChatService] Найдено количество {len(chats)} чатов для пользователя: {user_id}")
      return chats
    
    except Exception as e:
      logger.error(f"[ChatService] Ошибка получения чатов для пользователя {user_id}, ошибка: {e}")
      return []
    
    finally:
      if close_db and db:
        await db.close()


  @staticmethod
  async def get_user_chat_ids(user_id: int, db: Optional[AsyncSession] = None):
    """
    Получаем только ID чатов для пользователей (без загрузки объектов)
    Оптимизированная версия для WebSocket
    """

    close_db = False 
    if db is None:
      db = await get_db().__anext__()
      close_db = True 

    try: 
      # Более легкий запрос без загрузки отношений
      stmt = (
        select(ChatRoom.id)
        .join(ChatRoom.participants)
        .where(ChatRoom.participants.any(User.id == user_id))
        .order_by(desc(ChatRoom.created_at))
      )

      result = await db.execute(stmt)
      chat_ids = result.scalars().all()

      logger.debug(f"[ChatService] Пользователь {user_id} имеет IDs чат/чатов: {chat_ids}")
      return chat_ids 
    
    except Exception as e:
      logger.error(f"[ChatSerivce] Ошибка получения IDs чатов для пользователя {user_id}: {e}")
      return []
    
    finally:
      if close_db and db:
        await db.close()


  @staticmethod
  async def get_chat_members(chat_id: int, db: Optional[AsyncSession] = None) -> List[int]:
    """
    Получение ID всех участников чата

    Args:
      chat_id: ID чата
      db: Необязательная сессия в БД

    Returns:
      Список ID пользователей
    """

    close_db = False 
    if db is None:
      db = await get_db().__anext__()
      close_db = True

    try:
      stmt = (
        select(ChatRoom)
        .where(ChatRoom.id == chat_id)
        .options(selectload(ChatRoom.participants))
      )

      result = await db.execute(stmt)
      chat = result.scalar_one_or_none()

      if not chat:
        logger.warning(f"[ChatService] Чат {chat_id} не найден")
        return []
      
      # Извлекаем ID пользователей
      user_ids = [user.id for user in chat.participants]
      logger.debug(f"[ChatService] Чат {chat_id} содержит количество: {user_ids}")

      return user_ids
    
    except Exception as e:
      logger.error(f"[ChatService] Ошибка при получении списка участников чата: {e}")
      return []
    
    finally:
      if close_db and db:
        await db.close()