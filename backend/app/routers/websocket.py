import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from sqlalchemy import select

from app.database import get_db, AsyncSessionLocal
from app.websocket.manager import manager 
from app.models.participant import participants
from app.models.message import Message 
from app.schemas.message import MessageResponse
from app.dependencies.auth import get_current_user
from app.redis.manager import RedisManager
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/{chat_id}")
async def websocket_endpoint(
  websocket: WebSocket, 
  chat_id: int,
):
  """
  WebSocket эндпоинт для конкретного чата
  """

  logger.info(f"Новое подключение WebSocket к чату -> {chat_id}")

  # 1. Получаем токен из query-параметра
  token = websocket.query_params.get("token")
  if not token:
    logger.info(f"Нет токена в подключении к чату -> {chat_id}")
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return 
  
  logger.info(f"Токен получен для чата -> {chat_id}")
  
  # Создаем ссесию в БД
  async for db in get_db():
    try:
        # 2. Получаем пользователя по токену 
        try:
           # Аутентификация
           current_user = await get_current_user(token=token, db=db)
           logger.info(f"Пользователь {current_user['id']} аутентифицирован для чата {chat_id}")
        except Exception as e:
            logger.info(f"Ошибка аутентификации: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    
        # 3. Проверка участия в чате 
        result = await db.execute(
            select(participants).where(
                participants.c.user_id == current_user["id"],
                participants.c.chat_id == chat_id,
            )
        )

        if not result.first():
            logger.warning(f"Пользователь {current_user['id']} не участник чата {chat_id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return 
        
        logger.info(f"Проверка участия в чате пройдена для пользователя -> {current_user['id']}")
        
        # 4. Подключение к менеджеру
        await manager.connect(websocket, chat_id, current_user['id'])

        # 5. Подверждаем подключение пользователю
        await websocket.send_json({
            "type": "system",
            "message": "connected",
            "chat_id": chat_id,
            "user_id": current_user["id"],
        })
        logger.info(f"Отправлено подтверждение подключения пользователю -> {current_user['id']}")
        
        try:
            # 6. Держим соединение открым ДО отключения 
            while True:
                raw_data = await websocket.receive_text()
                # logger.info(f"Получены данные от пользователя {current_user.id}: {raw_data[:100]}...")

                # 7. Парсим JSON
                try:
                    data = json.loads(raw_data)
                    if data.get("type") != "message":
                        continue      # игнорируем неизвестные типы

                    content = data.get("content", "").strip()
                    if not content:
                        continue

                except json.JSONDecodeError:
                    await websocket.send_json({
                    "type": "error",
                    "message": "Неверный формат. Отправьте JSON"
                    })
                    continue

                try:
                    # Создаем и сохраняем сообщение
                    new_message = Message(
                        chat_id=chat_id,
                        sender_id=current_user["id"],
                        content=content,
                    )
                    db.add(new_message)
                    await db.commit()
                    await db.refresh(new_message)
                
                except Exception as e:
                    logger.error(f"Ошибка сохранения сообщения: {e}")
                    await db.rollback()
                    await websocket.send_json({
                        "type": "error",
                        "message": "Ошибка сохранения сообщения",
                    })
                    continue

                # 8. Создаем и отправляем ответ (ОСНОВНОЙ ПУТЬ)
                try:
                    # 9. Преобразуем в Pydantic-модель для сериализации
                    message_response = MessageResponse.model_validate(new_message)

                    # 10. Send-to-other всем в чате (включая отправителя)
                    payload = {
                        "sender_id": current_user["id"],
                        "type": "message",
                        "message": message_response.model_dump(),
                    }
                    await manager.send_to_other(payload, chat_id, websocket)
                
                except Exception as e:
                    logger.error(f"Критическая ошибка сериализации: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Внутренняя ошибка сервера",
                    })
                    # Закрываем соединение
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                    break 

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
    finally:
        await manager.disconnect(websocket, chat_id)


