from pydantic import BaseModel, ConfigDict
from datetime import datetime 


class MessageBase(BaseModel):
  """Схема сообщения"""

  content: str 


class MessageCreate(MessageBase):
  """Схема создания сообщения"""

  pass 


class MessageResponse(MessageBase):
  """Схема с информацией о сообщении"""

  id: int
  chat_id: int 
  sender_id: int 
  created_at: datetime 

  model_config = ConfigDict(from_attributes=True)