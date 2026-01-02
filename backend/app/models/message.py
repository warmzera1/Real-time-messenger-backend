from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func 
from app.models.base import Base


class Message(Base):
  """
  Модель сообщений
  """

  __tablename__ = "messages"

  id = Column(Integer, primary_key=True, index=True)
  chat_id = Column(Integer, ForeignKey("chat_rooms.id"), index=True)
  sender_id = Column(Integer, ForeignKey("users.id"), index=True)
  content = Column(String(2000), nullable=False)
  created_at = Column(DateTime(timezone=True), server_default=func.now())
