from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select, update, func

from app.models.message import Message, MessageEdit, MessageDelivery
from app.models.participant import participants
from app.services.chat_service import ChatService
from app.redis.manager import redis_manager
import logging

logger = logging.getLogger(__name__)


class MessageService:

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
      message = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        content=content,
      )

      db.add(message)             
      await db.flush()             

      participants = await ChatService().get_chat_members(chat_id, db)

      for participant_id in participants:
        if participant_id == sender_id:
          continue 

        delivery = MessageDelivery(
          message_id=message.id,
          user_id=participant_id,
          delivered_at=None,
        )
        db.add(delivery)

      await db.commit()
      await db.refresh(message)

      return message 
    
    except Exception as e:
      await db.rollback()     
      logger.error(f"[Create Message] Ошибка создания сообщения: {e}")
      return None 
    
    
  @staticmethod
  async def send_message(
    chat_id: int,
    sender_id: int,
    content: str,
    db: AsyncSession,
  ):
    
    await MessageService.ensure_user_in_chat(
      user_id=sender_id,
      chat_id=chat_id,
      db=db,
    )
  
    message = await MessageService.create_message(
      chat_id=chat_id,
      sender_id=sender_id, 
      content=content, 
      db=db
    )

    if not message:
      raise ValueError("MESSAGE_CREATE_FAILED")
  
    await redis_manager.publish_to_chat(
      chat_id=chat_id,
      message={
        "id": message.id,
        "chat_id": message.chat_id,
        "sender_id": message.sender_id,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
      }
    )

    return message
    

  @staticmethod
  async def get_chat_messages(
    chat_id: int,
    user_id: int,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
  ) -> list[Message]:
    """
    Возвращает последнее сообщение чата (с пагинацией)
    """

    await MessageService.ensure_user_in_chat(
      user_id=user_id,
      chat_id=chat_id,
      db=db,
    )

    stmt = (
      select(Message)
      .where(Message.chat_id == chat_id)
      .order_by(Message.created_at.desc())
      .limit(limit)
      .offset(offset)
    )

    result = await db.execute(stmt)
    return result.scalars().all()    
    

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

      return result.scalar_one_or_none()   
    
    except Exception as e:
      logger.error(f"[Get Message By ID] Ошибка получения сообщения: {e}")
      return None 
    

  @staticmethod
  async def mark_delivered(
    message_id: int,
    user_id: int,
    db: AsyncSession,
  ) -> bool:
    """Отмечает сообщение как доставленное"""

    result = await db.execute(
      update(MessageDelivery)
      .where(
        MessageDelivery.message_id == message_id,
        MessageDelivery.user_id == user_id,
        MessageDelivery.delivered_at.is_(None)
      )
      .values(delivered_at=func.now())
    )
  
    await db.commit()

    return result.rowcount > 0
    

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

    stmt = select(Message).where(
      Message.id == message_id,
      Message.is_deleted == False,
    )

    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
      raise ValueError("MESSAGE_NOT_FOUND")
    
    if message.sender_id != user_id:
      raise ValueError("FORBIDDEN")
    
    message.is_deleted = True
    await db.commit()
    return True
  

  @staticmethod 
  async def edit_message(
    message_id: int, 
    user_id: int, 
    new_content: str,
    db: AsyncSession
  ) -> bool:
    """Редактирование сообщения конкретного пользователя"""

    msg = await db.get(Message, message_id)
    if not msg or msg.is_deleted:
      raise ValueError("MESSAGE_NOT_FOUND")
    
    if msg.sender_id != user_id:
      raise ValueError("FORBIDDEN")
    
    old_content = msg.content 

    edit = MessageEdit(
      message_id=message_id,
      user_id=user_id,
      old_content=old_content,
      new_content=new_content,
      edited_at=func.now(),
    )
    db.add(edit)
    
    msg.content = new_content 
    msg.is_edited = True 

    await db.commit()
    return True 
  

  @staticmethod
  async def ensure_user_in_chat(
    user_id: int,
    chat_id: int,
    db: AsyncSession,
  ) -> None:
    """Состоит ли пользователь в чате"""

    is_member = await ChatService.is_user_in_chat(
      user_id=user_id,
      chat_id=chat_id,
      db=db,
    )

    if not is_member:
      raise ValueError("FORBIDDEN")
      

  

  


 