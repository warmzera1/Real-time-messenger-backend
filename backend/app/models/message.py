from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func 
from datetime import datetime
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
  delivered_at = Column(DateTime(timezone=True), nullable=True, index=True)
  read_at = Column(DateTime(timezone=True), nullable=True)
  created_at = Column(DateTime(timezone=True), server_default=func.now())

  # Связи
  sender = relationship("User", back_populates="sent_messages")
  chat = relationship("ChatRoom", back_populates="messages")
  read_by_users = relationship(
    "MessageRead",
    back_populates="message",
    cascade="all, delete-orphan"
  )


class MessageRead(Base):
  """
  Таблица для отслеживания прочтения сообщений пользователями
  Позволяет хранить, кто и когда прочитал сообщение
  """

  __tablename__ = "message_reads"

  id = Column(Integer, primary_key=True, index=True)
  message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
  read_at = Column(DateTime, default=datetime.utcnow)

  # Индекс для быстрого поиска
  __table_args__ = (
    UniqueConstraint("message_id", "user_id", name="uix_message_user"),
  )

  # Связи
  message = relationship("Message", back_populates="read_by_users")
  user = relationship("User", back_populates="read_messages")
