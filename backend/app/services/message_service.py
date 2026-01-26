from datetime import datetime 

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select, update, func

from app.models.message import Message
from app.models.participant import participants
from app.services.chat_service import ChatService
import logging



logger = logging.getLogger(__name__)


class MessageService:
  """
  Сервис для работы с сообщениями
  """

  @staticmethod 
  async def create_message(
    chat_id: int,
    sender_id: int,
    content: str,
    db: AsyncSession
  ) -> Optional[Message]:
    """
    Создание и сохранения сообщения
    """

    try:
      # Создаем объект сообщения
      message = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        content=content,
      )

      db.add(message)             # Добавляем в сессию
      await db.commit()           # Фиксируем изменения в БД
      await db.refresh(message)   # Обновляем объект из БД

      return message 
    
    except Exception as e:
      await db.rollback()         # Откатываем транзакцию при любой ошибке
      logger.error(f"[Create Message] Ошибка создания сообщения: {e}")
      return None 
    

  @staticmethod
  async def get_chat_messages(
    chat_id: int,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
  ) -> list[Message]:
    """
    Возвращает последнее сообщение чата (с пагинацией)
    """

    try:
      stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
      )

      result = await db.execute(stmt)
      return result.scalars().all()       # Возвращаем список объектов Message
    
    except Exception as e:
      logger.error(f"[Get Chat Messages] Ошибка получения сообщений чата {chat_id}: {e}")
      return []
    

  @staticmethod
  async def get_message_by_id(
    message_id: int,
    db: AsyncSession,
  ) -> Optional[Message]:
    """
    Находит одно сообщение по его ID
    """

    try:
      stmt = select(Message).where(Message.id == message_id)
      result = await db.execute(stmt)

      return result.scalar_one_or_none()    # Один объект или None 
    
    except Exception as e:
      logger.error(f"[Get Message By ID] Ошибка получения сообщения: {e}")
      return None 
    

  @staticmethod
  async def mark_delivered(
    message_id: int,
    db: AsyncSession,
  ) -> bool:
    """Отмечает сообщение как доставленное"""
    
    stmt = (
      update(Message)
      .where(
        Message.id == message_id,
        Message.delivered_at.is_(None),
      )
      .values(delivered_at=func.now())
      .returning(Message.id)
    ) 

    result = await db.execute(stmt)
    await db.commit()

    return bool(result.scalar_one_or_none())
  

  @staticmethod 
  async def mark_messages_as_read(
    message_ids: list[int],
    reader_id: int,
    db: AsyncSession
  ) -> int:
    """
    Отмечает несколько сообщений как прочитанные одним запросом
    Возвращает количество обновленных записей
    """

    if not message_ids:
      return 0
    
    stmt = (
      update(Message)
      .where(
        Message.id.in_(message_ids),
        Message.sender_id != reader_id,
        Message.read_at.is_(None),
        Message.chat_id.in_(
          select(participants.c.chat_id)
          .where(participants.c.user_id == reader_id)
        )
      )
      .values(read_at=func.now())
    )

    result = await db.execute(stmt)
    await db.commit()

    return result.rowcount
  

  @staticmethod 
  async def delete_message(
    message_id: int, 
    user_id: int, 
    db: AsyncSession
  ):
    """Удаление сообщения конкретного пользователя"""

    result = await db.execute(
      update(Message)
      .where(
        Message.id == message_id,
        Message.sender_id == user_id,
        Message.is_deleted == False,
      )
      .values(is_deleted=True)
    )

    if result.rowcount == 0:
      await db.rollback()
      return False

    await db.commit()
    return True
  

  


 