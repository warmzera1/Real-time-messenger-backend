from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime 
from app.models.base import Base 


class ChatRead(Base):
  """Модель последнего прочитанного сообщения в чате"""

  __tablename__ = "chat_reads"

  id = Column(Integer, primary_key=True)
  chat_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
  
  last_read_message_id = Column(Integer, nullable=True)
  read_at = Column(DateTime, default=datetime.utcnow)

  __table_args__ = (
    UniqueConstraint("chat_id", "user_id", name="uix_chat_user"),
  )