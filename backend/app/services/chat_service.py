from sqlalchemy import select, exists, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession 
from typing import List, Optional
import logging

from app.models.user import User
from app.models.chat import ChatRoom
from app.models.message import Message
from app.models.participant import participants 
from app.redis.manager import redis_manager

logger = logging.getLogger(__name__)


class ChatService:

  @staticmethod
  async def get_chat_members(chat_id: int, db: AsyncSession) -> list[int]:
    """Возвращает список ID пользователей - участников чата"""

    stmt = select(participants.c.user_id).where(        # Берем только user_id
      participants.c.chat_id == chat_id                 # из связывающей таблицы many-to-many
    )

    result = await db.execute(stmt)
    return result.scalars().all()
  

  @staticmethod 
  async def get_user_chat_ids(user_id: int, db: AsyncSession) -> list[int]:
    """Возвращает список ID чатов пользователя"""

    stmt = select(participants.c.chat_id).where(
        participants.c.user_id == user_id,
    ).distinct()

    result = await db.execute(stmt)
    return result.scalars().all()
  
  
  @staticmethod 
  async def is_user_in_chat(
    user_id: int,
    chat_id: int,
    db: AsyncSession,
  ) -> bool:
    """Проверка, является ли пользователь участником чата"""

    stmt = select(
      exists().where(
        participants.c.user_id == user_id,
        participants.c.chat_id == chat_id,
      )
    )

    result = await db.execute(stmt)
    return result.scalar()
  

  @staticmethod 
  async def find_or_create_private_chat(
    user1_id: int,
    user2_id: int,
    db: AsyncSession
  ) -> Optional[ChatRoom]:
    """
    Найти существующий личный чат или создать новый
    """

    try:
      # Поиск существующего чата
      existing_chat = await ChatService._find_private_chat(user1_id, user2_id, db)
      if existing_chat:
        return existing_chat
      
      # Создание нового чата
      chat = await ChatService.create_private_chat(user1_id, user2_id, db)

      return chat
    
    except Exception as e:
      logger.error(f"Ошибка создания чата: {e}")
      return None 


  @staticmethod 
  async def _find_private_chat(
    user1_id: int,
    user2_id: int,
    db: AsyncSession,
  ) -> Optional[ChatRoom]:
    """
    Поиск существующего личного чата
    """

    stmt = (
      select(ChatRoom)
      .join(participants)
      .where(ChatRoom.is_group == False)
      .where(participants.c.user_id.in_([user1_id, user2_id]))
      .group_by(ChatRoom.id)
      .having(func.count(participants.c.user_id.distinct()) == 2)
      .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
  

  @staticmethod
  async def create_private_chat(
    user1_id: int,
    user2_id: int,
    db: AsyncSession,
  ) -> Optional[ChatRoom]:
    """
    Создание нового личного чата
    """

    try:
      # Создаем чат
      chat = ChatRoom(name=None, is_group=False)
      db.add(chat)
      await db.flush()      # Получаем ID

      # Добавляем участников
      await db.execute(
        participants.insert().values([
          {"user_id": user1_id, "chat_id": chat.id},
          {"user_id": user2_id, "chat_id": chat.id},
        ])
      )

      await db.commit()
      await db.refresh(chat)

      await redis_manager.add_user_to_chat(user1_id, chat.id)
      await redis_manager.add_user_to_chat(user2_id, chat.id)

      return chat 
    
    except Exception as e:
      await db.rollback()
      logger.error(f"Ошибка создания чата: {e}")
      return None 


  @staticmethod
  async def search_users(
    query: str,
    exclude_user_id: int,
    limit: int,
    db: AsyncSession,
  ) -> list[User]:
    """
    Поиск пользователя по username
    """

    stmt = (
      select(User)
      .where(User.username.ilike(f"%{query}%"))
      .where(User.id != exclude_user_id)
      .where(User.is_active == True)
      .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
  




