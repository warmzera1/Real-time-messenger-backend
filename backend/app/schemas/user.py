from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
  """Схема для регистрации нового пользователя"""

  username: str = Field(min_length=3, max_length=50)
  email: EmailStr
  password: str = Field(min_length=8, max_length=72)


class UserResponse(BaseModel):
  """Схема с информацией данных пользователя (GET /users/{id})"""

  id: int
  username: str 
  email: EmailStr
  is_active: bool = True 
  created_at: datetime 

  # Позволяет создавать модели из объектов ORM
  model_config = ConfigDict(from_attributes=True)    


class LoginForm(BaseModel):
  """Схема для авторизации существующего пользователя"""

  username: str | None = None
  email: str | None = None
  password: str = Field(..., min_length=8)

  def get_identifier(self):
    return self.username or self.email