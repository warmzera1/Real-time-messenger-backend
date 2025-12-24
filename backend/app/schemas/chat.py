from pydantic import BaseModel, ConfigDict
from typing import Optional 
from datetime import datetime 


class ChatRoomBase(BaseModel):
  """Схема для чата"""

  name: Optional[str] = None      # None - для личных чатов
  is_group: bool = False


class ChatRoomCreate(ChatRoomBase):
  """Схема для создания чата"""

  pass 


class ChatRoomResponse(ChatRoomBase):
  """Схема с информацией о чате"""

  id: int 
  created_at: datetime 

  model_config = ConfigDict(from_attributes=True)