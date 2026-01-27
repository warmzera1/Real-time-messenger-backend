from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Boolean, Index
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
  read_at = Column(DateTime(timezone=True), nullable=True)
  created_at = Column(DateTime(timezone=True), server_default=func.now())
  is_deleted = Column(Boolean, nullable=False, default=False, server_default="false")
  is_edited = Column(Boolean, nullable=False, default=False, server_default="false")

  # Связи
  sender = relationship("User", back_populates="sent_messages")
  chat = relationship("ChatRoom", back_populates="messages")
  read_by_users = relationship(
    "MessageRead",
    back_populates="message",
    cascade="all, delete-orphan"
  )
  edits_history = relationship(
    "MessageEdit", 
    back_populates="message",
    cascade="all, delete-orphan"
  )
  deliveries = relationship(
    "MessageDelivery",
    back_populates="message",
    cascade="all, delete-orphan",
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


class MessageEdit(Base):
  """
  Таблица для отслеживания редактирования сообщений пользователями
  Позволяет хранить, кто и какое сообщение отредактировал
  """

  __tablename__ = "message_edits"

  id = Column(Integer, primary_key=True, index=True)
  message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
  old_content = Column(String(2000), nullable=False)
  new_content = Column(String(2000), nullable=False)
  edited_at = Column(DateTime, default=func.now())

  message = relationship("Message", back_populates="edits_history")
  user = relationship("User", back_populates="edited_messages")


class MessageDelivery(Base):
  """
  Таблица для отслеживания когда доставлено сообщение
  Позволяет хранить, когда и кому было доставлено сообщение
  """

  __tablename__ = "message_deliveries"

  id = Column(Integer, primary_key=True, index=True)
  message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
  delivered_at = Column(DateTime(timezone=True), nullable=True, default=None)

  __table_args__ = (
    UniqueConstraint("message_id", "user_id", name="uix_message_delivery_user"),
  )

  message = relationship("Message", back_populates="deliveries")
  user = relationship("User", back_populates="message_deliveries")


