from pydantic import BaseModel, ConfigDict, field_serializer
from datetime import datetime 


class MessageBase(BaseModel):
  """Схема сообщения"""

  content: str 
  chat_id: int


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

    
  # Комбинированная конфигурация
  model_config = ConfigDict(
      from_attributes=True,  # Для работы с ORM объектами (ранее orm_mode)
      str_strip_whitespace=True,
      validate_assignment=True,
  )

  @field_serializer("created_at")
  def serialize_created_at(self, created_at: datetime, _info):
    return created_at.isoformat()
  