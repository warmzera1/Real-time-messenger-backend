from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from app.schemas.user import UserResponse


class ChatRoomBase(BaseModel):
  """Схема для чата"""

  name: Optional[str] = Field(None, max_length=100)   
  

class ChatRoomCreate(ChatRoomBase):
  """Схема для создания чата"""

  second_user_id: int = Field(gt=0, description="ID второго пользователя")           


class ChatRoomResponse(BaseModel):
  """Схема с информацией о чате"""

  id: int 
  name: Optional[str]
  is_group: bool
  created_at: datetime
  participants: List[UserResponse]

  model_config = ConfigDict(from_attributes=True)


class ChatRoomIdResponse(BaseModel):
  """Схема с информацией существующих ID чатов у пользователя"""
    
  id: int