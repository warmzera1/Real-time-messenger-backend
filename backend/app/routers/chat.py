from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, select, desc
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db 
from app.schemas.chat import ChatRoomCreate, ChatRoomResponse
from app.schemas.user import UserResponse
from app.models.chat import ChatRoom
from app.models.participant import participants 
from app.dependencies.auth import get_current_user
from app.models.user import User 
from app.services.chat_services import ChatService


router = APIRouter(prefix="/chats", tags=["chats"])

@router.post("/", response_model=ChatRoomResponse)
async def create_chat(
  chat_data: ChatRoomCreate,
  response: Response,
  current_user: dict = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """
  Создание чата (личного)
  """

  # 1. Проверка, что второй пользователь не текущий
  if chat_data.second_user_id == current_user["id"]:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Нельзя создавать чат с самим собой",
    )
  
  # 2. Проверка существования второго пользователя
  result = await db.execute(
    select(User).where(User.id == chat_data.second_user_id)
  )
  second_user = result.scalar_one_or_none()
  
  # 3. Если нет - ошибка
  if not second_user:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Пользователь не найден",
    )
  
  # 4. Поиск существующего личного чата
  stmt = (
    select(ChatRoom)
    .join(participants)
    .where(ChatRoom.is_group == False)
    .where(participants.c.user_id.in_([current_user["id"], chat_data.second_user_id]))
    .group_by(ChatRoom.id)
    .having(func.count(participants.c.user_id.distinct()) == 2)
  )
  result = await db.execute(stmt)
  existing_chat = result.scalar_one_or_none()

  # 5. Если найден - возвращаем существующий чат
  if existing_chat:
    response.status_code = status.HTTP_200_OK
    return existing_chat
  
  # 6. Если нет - создаем
  new_chat = ChatRoom(name=None, is_group=False)
  db.add(new_chat)
  await db.commit()
  await db.refresh(new_chat)

  # 7. Добавляем обоих участников в БД
  stmt = select(User).where(User.id.in_([current_user["id"], chat_data.second_user_id]))
  result = await db.execute(stmt)
  users = result.scalars().all()

  new_chat.participants.extend(users)
  await db.commit()
  await db.refresh(new_chat, ["participants"])

  response.status_code = status.HTTP_201_CREATED
  # 8. Возвращаем чат
  return new_chat


@router.get("/", response_model=List[ChatRoomResponse])
async def get_user_chats(
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """
  Список чатов текущего пользователя
  """

  chat_service = ChatService()
  chats = await chat_service.get_user_chats(current_user["id"], db)
  return chats


@router.get("/search", response_model=List[UserResponse])
async def search_users(
  q: str = Query(..., min_length=2, description="Поисковой запрос"),
  current_user: dict = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  limit: int = 20,
):
  """Поиск пользователей по username (исключая текущего)"""

  stmt = (
    select(User)
    .where(User.username.ilike(f"%{q}%"))
    .where(User.id != current_user["id"])
    .limit(limit)
  )

  result = await db.execute(stmt)
  users = result.scalars().all()
  return users







