from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession 
from typing import List 

from app.database import get_db 
from app.schemas.message import MessageCreate, MessageResponse 
from app.models.user import User
from app.dependencies.auth import get_current_user 
from app.services.message_service import MessageService 
from app.services.chat_service import ChatService 
from app.redis.manager import redis_manager

router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/", response_model=MessageResponse)
async def send_message(
  request: MessageCreate,
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """Отправка сообщения"""

  # 1. Проверка участника чата
  is_member = await ChatService.is_user_in_chat(
    user_id=current_user.id,
    chat_id=request.chat_id,
    db=db
  )

  if not is_member:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Вы не являетесь участником чата"
    )
  
  # Создание сообщения в БД
  message = await MessageService.create_message(
    chat_id=request.chat_id,
    sender_id=current_user.id, 
    content=request.content, 
    db=db
  )

  if not message:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
      detail="Ошибка при создании сообщения")
  
  # Публикация в Redis для WebSocket рассылки
  await redis_manager.publish_chat_message(
    chat_id=request.chat_id,
    message_data={
      "id": message.id,
      "chat_id": message.chat_id,
      "sender_id": message.sender_id,
      "content": message.content,
      "created_at": message.created_at.isoformat(),
      "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
    }
  )

  return message


@router.get("/", response_model=List[MessageResponse])
async def get_messages(
  chat_id: int = Query(..., gt=0),
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  limit: int = Query(50, ge=1, le=100),
  offset: int = Query(0, ge=0),
):
  """Получение сообщений"""

  # Проверка участника 
  is_member = await ChatService.is_user_in_chat(
    user_id=current_user.id,
    chat_id=chat_id,
    db=db,
  )
  if not is_member:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Вы не являетесь участником чата",
    )
  
  # Получение сообщений через сервис
  messages = await MessageService.get_chat_messages(
    chat_id=chat_id,
    limit=limit,
    offset=offset,
    db=db,
  )

  return messages


@router.delete("/{message_id}/delete", status_code=204)
async def delete_message(
  message_id: int,
  current_user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
):
  """Удаление сообщения"""

  success = await MessageService.delete_message(
    message_id=message_id,
    user_id=current_user.id,
    db=db,
  )
  if not success:
    raise HTTPException(404, "Сообщение не найден или не ваше")
  


