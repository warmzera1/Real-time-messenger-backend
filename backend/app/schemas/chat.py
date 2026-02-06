from typing import List
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.user import UserResponse


class ChatRoomBase(BaseModel):
  """Базовая схема для чата"""

  name: str | None = Field(None, max_length=100, description="Название чата")  
  

class ChatRoomCreate(ChatRoomBase):
  """Схема для создания чата"""

  second_user_id: int = Field(gt=0, description="ID второго пользователя")           


class ChatRoomResponse(ChatRoomBase):
  """Схема с полной информацией о чате для ответа API"""

  id: int 
  is_group: bool = Field(description="Флаг группового чата")
  created_at: datetime
  participants: List[UserResponse]

  model_config = ConfigDict(from_attributes=True)


class ChatRoomIdResponse(BaseModel):
  """Схема с информацией существующих ID чатов у пользователя"""
    
  id: int