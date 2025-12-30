from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserResponse 
from app.dependencies.auth import get_current_user
from app.models.user import User 


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
  """Получение профиля текущего пользователя"""

  # current_user = await get_current_user()

  # if not current_user:
  #   raise HTTPException(
  #     status_code=status.HTTP_404_NOT_FOUND,
  #     detail="Пользователь не найден",
  #   )
  
  return current_user