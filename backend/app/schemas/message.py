from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class MessageBase(BaseModel):
  """Базовая схема сообщения"""

  content: str = Field(min_length=1, max_length=2000)
  chat_id: int = Field(gt=0)


class MessageCreate(MessageBase):
  """Схема создания сообщения"""

  pass 


class MessageEdit(BaseModel):
  """Схема изменения сообщения"""

  content: str = Field(min_length=1, max_length=2000)


class MessageResponse(MessageBase):
  """Схема с информацией о сообщении"""

  id: int
  sender_id: int
  created_at: datetime
  delivered_at: datetime | None = None
  read_at: datetime | None = None
  is_delete: bool = False

  model_config = ConfigDict(
      from_attributes=True,  
      str_strip_whitespace=True,
      validate_assignment=True,
  )

  