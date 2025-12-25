from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc 
from typing import List
from app.database import get_db 
from app.schemas.message import MessageCreate, MessageResponse
from app.models.message import Message
from app.models.participant import participants
from app.dependencies.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
  chat_id: int,
  message_data: MessageCreate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """
  Отправка сообщений в чат
  """

  # 1. Проверяем, является ли пользователь участником конкретного чата
  is_participant = (
    db.query(participants)
    .filter(
      participants.c.user_id == current_user.id,
      participants.c.chat_id == chat_id,
    )
    .first()
  )

  # Если нет - ошибка
  if not is_participant:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Вы не являетесь участником этого чата",
    )
  
  # Создаем сообщение
  new_message = Message(
    chat_id=chat_id,
    sender_id=current_user.id,
    content=message_data.content,
  )

  # Добавляем в БД и сохраняем
  db.add(new_message)
  db.commit()
  db.refresh(new_message)

  # Возвращаем новое сообщение
  return new_message


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(
  chat_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
  limit: int = 50,
  offset: int = 0,
):
  """
  Получение сообщений чата
  """

  # Проверяем, является ли пользователь участником конкретного чата
  is_participant = (
    db.query(participants)
    .filter(
      participants.c.user_id == current_user.id,
      participants.c.chat_id == chat_id,
    )
    .first()
  )

  # Если нет - ошибка
  if not is_participant:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Вы не являетесь участником чата",
    )
  
  # Получение сообщение
  messages = (
    db.query(Message)
    .filter(Message.chat_id == chat_id)
    .order_by(desc(Message.created_at))
    .limit(limit)
    .offset(offset)
    .all()
  )

  # Возвращаем ответ с сообщениями
  return messages 