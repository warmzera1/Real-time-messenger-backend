from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func 
from sqlalchemy.orm import relationship
from app.models.base import Base 


class User(Base):
  """
  Модель пользователя 
  """

  __tablename__ = "users"

  id = Column(Integer, primary_key=True, index=True)
  username = Column(String(50), unique=True, nullable=False, index=True)
  email = Column(String(255), unique=True, nullable=False, index=True)
  hashed_password = Column(String(255), nullable=False)
  is_active = Column(Boolean, default=True)
  created_at = Column(DateTime(timezone=True), server_default=func.now())

  # Связи
  chats = relationship(
    "ChatRoom",
    secondary="participants",     
    back_populates="participants",    
    lazy="selectin",
  )

  sent_messages = relationship("Message", back_populates="sender")
  read_messages= relationship("MessageRead", back_populates="user")
  edited_messages = relationship("MessageEdit", back_populates="user")
  message_deliveries = relationship("MessageDelivery", back_populates="user")

