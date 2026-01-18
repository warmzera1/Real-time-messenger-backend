from pydantic import BaseModel 


class TokenResponse(BaseModel):
  """Схема для ответа на успешный логин/refresh"""

  access_token: str 
  refresh_token: str 
  token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
  """Схема для refresh токена"""

  refresh_token: str


class LogoutRefreshTokenRequest(BaseModel):
  refresh_token: str