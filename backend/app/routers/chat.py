from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, select, desc
from typing import List

from app.database import get_db 
from app.schemas.chat import ChatRoomCreate, ChatRoomResponse
from app.models.chat import ChatRoom
from app.models.participant import participants 
from app.dependencies.auth import get_current_user
from app.models.user import User 


router = APIRouter(prefix="/chats", tags=["chats"])

@router.post("/", response_model=ChatRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
  chat_data: ChatRoomCreate,
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """
  Создание чата (личного)
  """

  # 1. Проверка, что второй пользователь не текущий
  if chat_data.second_user_id == current_user.id:
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
    .where(participants.c.user_id.in_([current_user.id, chat_data.second_user_id]))
    .group_by(ChatRoom.id)
    .having(func.count(participants.c.user_id.distinct()) == 2)
  )
  result = await db.execute(stmt)
  existing_chat = result.scalar_one_or_none()

  # 5. Если найден - возвращаем существующий чат
  if existing_chat:
    result = await db.execute(select(ChatRoom).where(ChatRoom.id == existing_chat.id))
    return result.scalar_one()
  
  # 6. Если нет - создаем
  new_chat = ChatRoom(name=None, is_group=False)
  db.add(new_chat)
  await db.commit()
  await db.refresh(new_chat)

  # 7. Добавляем обоих участников в БД 
  db.execute(
    participants.insert().values([
      {"user_id": current_user.id, "chat_id": new_chat.id},
      {"user_id": chat_data.second_user_id, "chat_id": new_chat.id}
    ])
  )
  await db.commit()

  # 8. Возвращаем чат
  return new_chat


@router.get("/", response_model=List[ChatRoomResponse])
async def get_user_chats(
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """
  Список чатов текущего пользователя
  1. Получаем объект чатов
  2. Присоединяем к объекту таблицу участников
  3. Соединяем там, где ID совпадает с chat_id в таблице участников 
  4. Фильтруем по конкретным участникам чата
  5. Возвращаем список чатов
  """

  stmt = (
    select(ChatRoom)
    .join(participants, ChatRoom.id == participants.c.chat_id)
    .where(participants.c.user_id == current_user.id)
    .order_by(desc(ChatRoom.created_at))
  )
  result = await db.execute(stmt)
  chats = result.scalars().all()
  return chats







