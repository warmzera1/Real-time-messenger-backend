from pydantic import BaseModel, ConfigDict, Field, field_serializer
from datetime import datetime
from typing import Optional


class MessageBase(BaseModel):
  """Схема сообщения"""

  content: str = Field(min_length=1, max_length=2000)
  chat_id: int = Field(gt=0)


class MessageCreate(MessageBase):
  """Схема создания сообщения"""

  pass 


class MessageResponse(BaseModel):
  """Схема с информацией о сообщении"""

  id: int
  chat_id: int
  sender_id: int
  content: str 
  created_at: datetime
  delivered_at: Optional[datetime] = None
  read_at: datetime 
  is_delete: bool 

    
  # Комбинированная конфигурация
  model_config = ConfigDict(
      from_attributes=True,  # Для работы с ORM объектами
      str_strip_whitespace=True,
      validate_assignment=True,
  )

  @field_serializer("created_at")
  def serialize_created_at(self, created_at: datetime, _info):
    return created_at.isoformat()
  