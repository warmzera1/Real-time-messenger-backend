from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select
from typing import List

from app.database import get_db 
from app.schemas.message import MessageCreate, MessageResponse
from app.models.message import Message
from app.models.participant import participants
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.websocket.manager import websocket_manager
from app.services.message_service import create_and_distribute_message



router = APIRouter(prefix="/messages", tags=["messages"])

# @router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
# async def send_message(
#   chat_id: int,
#   message_data: MessageCreate,
#   current_user: dict = Depends(get_current_user),
#   db: AsyncSession = Depends(get_db),
# ):
#   """
#   Отправка сообщений в чат
#   """

#   # 1. Проверяем, является ли пользователь участником конкретного чата
#   result = await db.execute(
#     select(participants).where(
#       participants.c.user_id == current_user["id"],
#       participants.c.chat_id == chat_id,
#     )
#   )

#   # Если нет - ошибка
#   if not result.first():
#     raise HTTPException(
#       status_code=status.HTTP_403_FORBIDDEN,
#       detail="Вы не являетесь участником этого чата",
#     )
  
#   # Создаем сообщение
#   new_message = Message(
#     chat_id=chat_id,
#     sender_id=current_user["id"],
#     content=message_data.content,
#   )

#   # Добавляем в БД и сохраняем
#   db.add(new_message)
#   await db.commit()
#   await db.refresh(new_message)

#   # Возвращаем новое сообщение
#   return new_message


@router.post("/", response_model=MessageResponse)
async def send_message(
  request: MessageCreate,
  current_user: dict = Depends(get_current_user),
  db: AsyncSession = Depends(get_db)
):
  """
  Отправка сообщений
  """

  message = await create_and_distribute_message(
    chat_id=request.chat_id,
    sender_id=current_user["id"],
    content=request.content,
    db=db
  )

  return message


@router.get("/", response_model=List[MessageResponse])
async def get_messages(
  chat_id: int = Query(..., description="ID чата"),
  current_user: dict = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  limit: int = 50,
  offset: int = 0,
):
  """
  Получение сообщений чата
  """

  # Проверяем, является ли пользователь участником конкретного чата
  is_participant = await db.execute(
    select(participants).where(
      participants.c.user_id == current_user["id"],
      participants.c.chat_id == chat_id,
    )
  )

  # Если нет - ошибка
  if not is_participant.first():
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Вы не являетесь участником чата",
    )
  
  # Получение сообщение
  stmt = (
    select(Message)
    .where(Message.chat_id == chat_id)
    .order_by(desc(Message.created_at))
    .limit(limit)
    .offset(offset)
  )
  result = await db.execute(stmt)
  messages = result.scalars().all()

  # Возвращаем ответ с сообщениями
  return messages 


@router.get("/{message_id}/read-status")
async def get_message_read_status(
  message_id: int,
  current_user: dict = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """
  Получение информации о том, кто прочитал сообщение
  """

  from app.services.message_service import MessageService

  # Проверяем, что пользователь имеет доступ к сообщению
  stmt = select(Message).where(Message.id == message_id)
  result = await db.execute(stmt)
  message = result.scalar_one_or_none()

  if not message:
    raise HTTPException(
      status_code=404,
      detail="Сообщение не найдено",
    )
  
  # Проверяем, что пользователь участник чата
  is_participant = await db.execute(
    select(participants).where(
      participants.c.user_id == current_user["id"],
      participants.c.chat_id == message.chat_id,
    )
  )

  if not is_participant.first():
    raise HTTPException(
      status_code=403,
      detail="Нет доступа",
    )
  
  # Получаем статус прочтения
  read_status = await MessageService.get_message_read_status(message_id, db)

  return read_status