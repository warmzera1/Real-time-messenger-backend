import logging
from sqlalchemy.exc import IntegrityError 
from app.database import get_db_session
from app.models.message import MessageRead, Message
from app.services.chat_service import ChatService 

logger = logging.getLogger(__name__)


class ReadService:
  """Сервис для работы с прочтением сообщений"""
  
  @staticmethod 
  async def mark_read(message_id: int, user_id: int) -> bool:
    """
    Сообщение прочитано
    """

    async with get_db_session() as db:
      # 1. Получаем сообщение
      message = await db.get(Message, message_id)
      if not message:
        return False 
      
      # 2. Проверяем, что пользователь участник чата
      is_member = await ChatService().is_user_in_chat(
        user_id=user_id, 
        chat_id=message.chat_id,
        db=db,
      )
      if not is_member:
        return False 
      
      # 3. Пишем факт прочтения
      read = MessageRead(
        message_id=message_id,
        user_id=user_id,
      )

      try:
        db.add(read)
        await db.commit()
        return True 
      
      except IntegrityError:
        # Уже прочитано (idempotency)
        await db.rollback()
        return False 
      
      except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка READ: {e}")
        return False 