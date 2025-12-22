from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func 
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