from typing import List 

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession 

from app.database import get_db 
from app.schemas.message import MessageCreate, MessageResponse, MessageEdit
from app.models.user import User
from app.dependencies.auth import get_current_user 
from app.services.message_service import MessageService 
from app.redis.manager import redis_manager

router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/", response_model=MessageResponse)
async def send_message(
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Отправка сообщения"""

    try:
        return await MessageService.send_message(
            chat_id=request.chat_id,
            sender_id=current_user.id,
            content=request.content,
            db=db
        )
    except ValueError as e:
        mapping = {
            "FORBIDDEN": 403,
            "MESSAGE_CREATE_FAILED": 500,
        }
        raise HTTPException(
            status_code=mapping.get(str(e), 500),
            detail=str(e)
        )


@router.get("/", response_model=List[MessageResponse])
async def get_messages(
    chat_id: int = Query(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Получение сообщений"""

    try:  
        return await MessageService.get_chat_messages(
            chat_id=chat_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            db=db,
        )
    except ValueError as e:
        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=403,
                detail="Вы не являетесь участником чата"
            )


@router.delete("/{message_id}/delete", status_code=204)
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удаление сообщения"""

    try: 
        await MessageService.delete_message(
            message_id=message_id,
            user_id=current_user.id,
            db=db,
        )
    except ValueError as e:
        if str(e) == "MESSAGE_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail="Сообщение не найдено"
            )
        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=403,
                detail="Сообщение не принадлежит Вам"
            )

  
@router.patch("/{message_id}/edit")
async def edit_message(
    request: MessageEdit,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Изменение сообщения"""

    try: 
        await MessageService.edit_message(
            message_id=message_id,
            user_id=current_user.id,
            new_content=request.content,
            db=db,
        )
    except ValueError as e:
        if str(e) == "MESSAGE_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail="Сообщение не найдено"
            )
        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=403,
                detail="Сообщение не принадлежит Вам"
            )

  


