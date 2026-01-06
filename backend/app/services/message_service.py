from datetime import datetime 
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select, update, and_ 
import logging 


from app.models.message import Message, MessageRead
from app.database import get_db


logger = logging.getLogger(__name__)


class MessageService:
  """
  Сервис для работы с сообщениями и статусами прочтения
  """

  @staticmethod 
  async def mark_as_read(
    message_id: int, 
    user_id: int,
    db: Optional[AsyncSession] = None 
  ) -> bool:
    """
    Пометить сообщение как прочитанное пользователем

    Returns:
      True - если сообщение помечено как прочитанное
      False - если сообщение уже было прочитано или ошибка
    """

    close_db = False 
    if db is None:
      db = await get_db().__anext__()
      close_db = True 

    try: 
      # 1. Не прочитано ли уже сообщение
      stmt = select(MessageRead).where(
        and_(
          MessageRead.message_id == message_id,
          MessageRead.user_id == user_id,
        )
      )
      result = await db.execute(stmt)
      existing_read = result.scalar_one_or_none()

      if existing_read:
        logging.debug(f"[Mark As Read] Сообщние {message_id} уже прочитано пользователем: {user_id}")
        return False 
      
      # 2. Создаем запись о прочтении
      message_read = MessageRead(
        message_id=message_id,
        user_id=user_id,
        read_at=datetime.utcnow(),
      )
      db.add(message_read)

      # 3. Обновляем поле read_at в самом сообщении
      await db.execute(
        update(Message)
        .where(Message.id == message_id)
        .values(read_at=datetime.utcnow())
      )

      await db.commit()

      logger.info(f"[Mark As Read] Сообщение {message_id} уже прочитано пользователем {user_id}")
      return True 
    
    except Exception as e:
      await db.rollback()
      logger.error(f"[Mark As Read] Ошибка в сообщение {message_id} как: {e}")
      return False 
    
    finally:
      if close_db and db:
        db.close()


  @staticmethod
  async def mark_chat_as_read(
    chat_id: int,
    user_id: int,
    db: Optional[AsyncSession] = None
  ) -> int:
    """
    Пометить ВСЕ непрочитанные сообщения в чате как прочитанные

    Returns:
      Количество помечанных сообщений
    """

    close_db = False 
    if db is None:
      db = await get_db().__anext__()
      close_db = True 

    try:
      # 1. Находим ВСЕ непрочитанные сообщения в чате
      subquery = select(Message.id).where(
        and_(
          Message.chat_id == chat_id,
          Message.sender_id != user_id,   # Не свои сообщения
        )
      ).except_(
        select(MessageRead.message_id).where(
          MessageRead.user_id == user_id,
        )
      )

      result = await db.execute(subquery)
      unread_message_ids = result.scalars().all()

      if not unread_message_ids:
        logger.error(f"[Mark Chat As Read] Нет не прочитанных сообщений в чате {chat_id} у пользователя {user_id}")
        return 0 
      
      # 2. Создаем записи о прочтении
      now = datetime.utcnow()
      message_reads = []

      for msg_id in unread_message_ids:
        message_reads.append(MessageRead(
          message_id=msg_id,
          user_id=user_id,
          read_at=now,
        ))

      db.add_all(message_reads)

      # 3. Обновляем read_at для последнего сообщения в чате
      last_message_stmt = select(Message.id).where(
        Message.chat_id == chat_id
      ).order_by(Message.created_at.desc()).limit(1)

      last_message_result = await db.execute(last_message_stmt)
      last_message_id = last_message_result.scalar_one_or_none()

      if last_message_id:
        await db.execute(
          update(Message)
          .where(Message.id == last_message_id)
          .values(read_at=now)
        )

      await db.commit()

      count = len(unread_message_ids)
      logger.info(f"[Mark Chat As Read] Количество {count} отмеченных сообщений как прочитанных в чате {chat_id} у пользователя {user_id}")

      return count 
    
    except Exception as e:
      await db.rollback()
      logger.error(f"[Mark Chat As Read] Ошибка при пометке 'прочитано' в чате {chat_id}: {e}")
      return 0
    
    finally:
      if close_db and db:
        await db.close()


  @staticmethod 
  async def get_message_read_status(
    message_id: int, 
    db: Optional[AsyncSession] = None
  ) -> List[dict]:
    """
    Получить информацию о том, кто прочитал сообщение
    """

    close_db = False 
    if db is None:
      db = await get_db().__anext__()
      close_db = True 

    try: 
      stmt = select(MessageRead).where(
        MessageRead.message_id == message_id
      ).order_by(MessageRead.read_at)

      result = await db.execute(stmt)
      reads = result.scalars().all()

      return [
        {
          "user_id": read.user_id,
          "read_at": read.read_at.isoformat(),
          "username": read.username if read.user else None 
        }
        for read in reads
      ]
    
    except Exception as e:
      logger.error(f"Ошибка получения информации о том кто прочитал сообщение {message_id}: {e}")
      return []
    
    finally:
      if close_db and db:
        await db.close()

  
  @staticmethod
  async def get_message_info(message_id: int) -> Optional[dict]:
    """
    Получить базовую информацию о сообщении
    """

    close_db = False 
    db = None 

    try: 
      db = await get_db().__anext__()
      close_db = True 

      stmt = select(Message).where(Message.id == message_id)
      result = await db.execute(stmt)
      message = result.scalar_one_or_none()

      if not message:
        return None 
      
      return {
        "id": message.id,
        "chat_id": message.chat_id,
        "sender_id": message.sender_id,
        "content": message.content,
        "created_at": message.created_at,
        "read_at": message.read_at, 
      }
    
    except Exception as e:
      logger.error(f"Ошибка получения информации о сообщении {message_id}: {e}")
      return None 
    
    finally:
      if close_db and db:
        await db.close()


  @staticmethod
  async def create_and_distribute_message(
    chat_id: int,
    sender_id: int,
    content: str,
    db: AsyncSession
  ):
    """
    Создать сообщение и рассылать через WebSocket
    """
    # 1. Сохраняем в БД
    message = Message(
      chat_id=chat_id,
      sender_id=sender_id,
      content=content,
      delivered_at=datetime.utcnow()
    )

    db.add(message)
    await db.flush()

    # 2. Получаем участников чата
    from app.services.chat_services import ChatService
    chat_service = ChatService()
    members = await chat_service.get_chat_members(chat_id, db)

    # 3. Подготавливаем данные
    message_data = {
      "id": message.id,
      "chat_id": message.chat_id,
      "sender_id": message.sender_id,
      "content": message.content,
      "created_at": message.created_at,
      "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None
    }

    # 4. Отправляем через WebSocket
    from app.websocket.manager import websocket_manager
    
    for member_id in members:
      await websocket_manager.send_to_user(
        member_id, {
          "type": "new_message",
          "chat_id": chat_id,
          "message": message_data,
        }
      )

    await db.commit()
    return message