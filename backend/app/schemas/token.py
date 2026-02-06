from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
  """Схема для ответа на успешный логин/refresh"""

  access_token: str 
  refresh_token: str 
  token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
  """Схема для работы с refresh токеном"""

  refresh_token: str = Field(..., description="JWT refresh_token")


class LogoutRefreshTokenRequest(BaseModel):
  refresh_token: str