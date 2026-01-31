from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select
from typing import List 

from app.database import get_db 
from app.schemas.chat import ChatRoomCreate, ChatRoomResponse, ChatRoomIdResponse
from app.schemas.user import UserResponse 
from app.dependencies.auth import get_current_user
from app.models.user import User 
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])

@router.post("/", response_model=ChatRoomResponse)
async def create_chat(
  chat_data: ChatRoomCreate,
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """
  Создание личного чата
  Возвращает существующий чат, если он УЖЕ есть
  """
  
  try:
    return await ChatService.find_or_create_private_chat(
      user1_id=current_user.id,
      user2_id=chat_data.second_user_id,
      db=db,
    )
  except ValueError as e:
    mapping = {
      "SELF_CHAT": 400,
      "USER_NOT_FOUND": 404,
      "CHAT_CREATE_FAILED": 500,
    }
    raise HTTPException(
      status_code=mapping.get(str(e), 500),
      detail=str(e)
    )


@router.get("/", response_model=List[ChatRoomIdResponse])
async def get_user_chats(
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """
  Список чатов пользователя
  """

  chats = await ChatService.get_user_chat_ids(current_user.id, db)
  return [{"id": chat_id} for chat_id in chats]


@router.get("/search", response_model=List[UserResponse])
async def search_users(
  q: str = Query(..., min_length=2, description="Поиск пользователя"),
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  limit: int = Query(20, ge=1, le=100)
):
  """
  Поиск пользователя (исключая текущего)
  """

  users = await ChatService.search_users(
    query=q,
    exclude_user_id=current_user.id,
    limit=limit,
    db=db,
  )

  return users
