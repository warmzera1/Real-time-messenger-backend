from sqlalchemy import select 
from sqlalchemy.ext.asyncio import AsyncSession 
from app.database import get_db_session
from app.models.chat_reads import ChatRead
from datetime import datetime 
import logging

logger = logging.getLogger(__name__)


class ChatReadService:
  """Сервис для отслеживания, до какого сообщения пользователь прочитал чат"""

  @staticmethod 
  async def mark_chat_read(
    chat_id: int,
    user_id: int, 
    last_read_message_id: int,
    db: AsyncSession,
  ):
    """Обновляет last_read_message_id, если он меньше нового"""

    stmt = (
      select(ChatRead).where(
        ChatRead.chat_id == chat_id,
        ChatRead.user_id == user_id
      )
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if record:
      if record.last_read_message_id is None or last_read_message_id > record.last_read_message_id:
        record.last_read_message_id = last_read_message_id
        record.read_at = datetime.utcnow()
    else:
      record = ChatRead(
        chat_id=chat_id,
        user_id=user_id,
        last_read_message_id=last_read_message_id,
      )
      db.add(record)
    
    await db.commit()
