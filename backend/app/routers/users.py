from fastapi import APIRouter, Depends

from app.schemas.user import UserResponse 
from app.dependencies.auth import get_current_user
 


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
  """Получение профиля текущего пользователя"""
  
  return current_user

