from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func 
from app.models.base import Base 


class ChatRoom(Base):
  """
  Модель чата/комната
  """

  __tablename__ = "chat_rooms"

  id = Column(Integer, primary_key=True, index=True)
  name = Column(String(100), nullable=True)
  is_group = Column(Boolean, default=False)
  created_at = Column(DateTime(timezone=True), server_default=func.now())