from pydantic import BaseModel 


class TokenResponse(BaseModel):
  """Схема для ответа на успешный логин/refresh"""

  access_token: str 
  refresh_token: str 
  token_type: str = "bearer"