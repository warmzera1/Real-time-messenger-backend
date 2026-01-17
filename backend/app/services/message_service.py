from datetime import datetime 
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select, update

from app.models.message import Message
from app.rabbit.manager import rabbit_manager
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

      # Event: message.created
      await rabbit_manager.publish_event(
        routing_key="message.created",
        payload={
          "message_id": message.id,
          "chat_id": chat_id,
          "sender_id": sender_id,
          "content": message.content,
          "created_at": message.created_at.isoformat(),
        }
      )

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
  async def mark_as_delivered(message_id: int, db: AsyncSession) -> bool:
    """
    Атомарно отмечает сообщение как доставленное
    Обновляет delivered_at ТОЛЬКО если поле еще null
    True - если обновление произошло, False - если уже было доставлено или
    """

    try:
      stmt = (
        update(Message)
        .where(
          Message.id == message_id,
          Message.delivered_at.is_(None)    # Только если еще не доставлено
      ).values(
        delivered_at=datetime.utcnow())
      )

      result = await db.execute(stmt)
      await db.commit()

      rows_updated = result.rowcount

      if rows_updated > 0:
        logger.info("Сообщение {message_id} отмечено как доставлено")
        return True 
      
    except Exception as e:
      await db.rollback()
      logger.error(f"Ошибка обновления статуса доставки: {e}")
      return False 
  

 