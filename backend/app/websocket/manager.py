import logging 
from datetime import datetime 
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from app.core.config import settings 
from app.redis.manager import redis_manager
from app.services.chat_service import ChatService 
from app.services.message_service import MessageService
from app.database import get_db_session

logger = logging.getLogger(__name__)


class WebSocketManager:
  """
  Управляет активными WebSocket-соединениями 
  Один пользователь -> одно активное соединение
  """

  def __init__(self):
    # user_id -> WebSocket
    self.connections: Dict[int, WebSocket] = {}

  
  async def connect(self, ws: WebSocket):
    """
    1. Аутентификация по JWT из query-параметра
    2. Если уже есть соединение -> закрываем старое
    3. Сохраняем новое
    4. Отправляем приветствие
    5. Отмечаем пользователя онлайн в Redis
    6. Отправляем накопленные оффлайн-сообщения 
    """

    try:
      user_id = await self._authenticate(ws)

      # Закрываем предыдущее соединение, если было
      if user_id in self.connections:
        try:
          await self.connections[user_id].close()
        except:
          pass 

      self.connections[user_id] = ws 

      # Синхронизуем членство в чатах
      await self._sync_chat_memberships(user_id)

      # Приветственное сообщение
      await ws.send_json({
        "type": "connected",
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
      })

      # Отмечаем онлайн в Redis (TTL ~ 60-90 сек)
      await redis_manager.mark_user_online(user_id)

      # Доставляем оффлайн-сообщения
      await self._send_pending_messages(user_id, ws)

      logger.info(f"Пользователь {user_id} подключен")

      return True

    except Exception as e:
      logger.warning(f"Подключение неудалось: {e}")
      await ws.close(code=1008) 
      return False 

  
  async def disconnect(self, ws: WebSocket):
    """
    Удаляем соединение и отмечаем пользователя оффлайн
    """

    user_id = None
    for uid, active_ws in list(self.connections.items()):
      if active_ws == ws:
        user_id = uid
        break 

    if user_id:
      del self.connections[user_id]
      await redis_manager.mark_user_offline(user_id)
      logger.info(f"Пользователь {user_id} отключился")

  
  async def receive_loop(self, ws: WebSocket):
    """
    Основной цикл чтения сообщения от клиента
    """

    user_id = self._find_user_by_ws(ws)
    if not user_id:
      await ws.close()
      return 
    
    try:
      while True:
        data = await ws.receive_json()

        msg_type = data.get("type")

        if msg_type == "message":
          await self._handle_user_message(user_id, data)

        elif msg_type == "read":
          await self._handle_read_message(user_id, data)
        else:
          logger.debug(f"Неизвестный тип сообщения: {msg_type}")
        
    except WebSocketDisconnect:
      await self.disconnect(ws)
    except Exception as e:
      logger.error(f"Ошибка в receive loop: {e}")
      await self.disconnect(ws)


  async def _handle_user_message(self, user_id: int, data: dict):
    """
    Обрабатывает сообщение от пользователя:
    - базовая валидация
    - публикация в Redis каналы
    - отправка сообщения отправителю (чтобы увидел свое сообщение)
    """

    chat_id = data.get("chat_id")
    content = (data.get("content") or "").strip()

    if not chat_id or not content:
      await self._send_error(
        user_id, 
        "Требуется указать chat_id и непустое содержимое текста"
      )

    async with get_db_session() as db:
      # Проверка участия
      if not await ChatService().is_user_in_chat(user_id, chat_id, db):
        await self._send_error(user_id, "Вы не являетесь участников чата")
        return 
      
      # Сохраняем в БД
      message_obj = await MessageService().create_message(
        chat_id=chat_id,
        sender_id=user_id,
        content=content,
        db=db,
      )
      if not message_obj:
        await self._send_error(user_id, "Ошибка при сохранении сообщения")
        return

      # Формируем payload для отправки
      message = {
        "id": message_obj.id,
        "chat_id": chat_id,
        "sender_id": user_id,
        "content": content,
        "created_at": message_obj.created_at.isoformat(),
      }

    # Публием в Redis -> все инстансы получат
    await redis_manager.publish_to_chat(chat_id, message)

    # Показываем отправителю сразу
    await self.send_to_user(user_id, {
      "type": "message",
      "message": message,
    })


  async def _handle_read_message(self, user_id: int, data: dict):
    """Обработка отметки сообщения как прочитанного"""

    message_id = data.get("message", {}).get("id")
    if not message_id:
      logger.warning(f"Пользователь {user_id} отправленно прочтение без ID")
      return 
    
    async with get_db_session() as db:
      await MessageService.mark_as_read(message_id, user_id, db)


  async def send_to_user(self, user_id: int, payload: dict) -> bool:
    """
    Отправляет данные конкретному пользователю, если он онлайн
    Возвращает успех отправки
    """

    ws = self.connections.get(user_id)
    if not ws:
      return False 
    
    try:
      await ws.send_json(payload)
      return True 
    except Exception:
      await self.disconnect(ws)
      return False 
    

  async def broadcast_to_chat(self, chat_id: int, message: dict):
    """
    Рассылает сообщение всем онлайн-участникам чата (кроме отправителя)
    Для определения участников используем Redis set - chat_members:{chat_id}
    """

    # Получаем всех участников чата (онлайн + оффлайн)
    members_key = f"chat_members:{chat_id}"
    member_ids = await redis_manager.redis.smembers(members_key)

    if not member_ids:
      return 
    
    sender_id = message.get("sender_id")

    async with get_db_session() as db:

      for member_str in member_ids:
        try:
          member_id = int(member_str)
          logger.info(f"Пытаемся отправить user {member_id} (онлайн: {await redis_manager.is_user_online(member_id)})")
          if member_id == sender_id:
            continue        # Отправителю уже отправили ранее

          # Проверяем, онлайн ли участник
          if await redis_manager.is_user_online(member_id):
            await self.send_to_user(member_id, {
              "type": "message",
              "message": message,
            })

            await MessageService.mark_delivered(message["id"], db)
          else:
            await redis_manager.store_offline_message(member_id, message)


        except ValueError:
          continue 

    logger.info(f"Broadcast chat {chat_id}: sender {sender_id}, members {member_ids}")


  async def _authenticate(self, ws: WebSocket) -> int:
    token = ws.query_params.get("token")
    if not token:
      raise WebSocketDisconnect("Требуется токен")
    
    try:
      payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
      )
      return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
      raise WebSocketDisconnect("Невалидный токен")
    
  
  def _find_user_by_ws(self, ws: WebSocket) -> int | None:
    for uid, active in self.connections.items():
      if active == ws:
        return uid 
    return None 
  

  async def _send_pending_messages(self, user_id: int, ws: WebSocket):

    async with get_db_session() as db:
      messages = await redis_manager.get_and_remove_offline_messages(user_id)
      for msg in messages:
        await ws.send_json({
          "type": "message",
          "message": msg,
        })

        await MessageService.mark_delivered(msg["id"], db)


  async def _sync_chat_memberships(self, user_id: int):
    async with get_db_session() as db:
      chat_ids = await ChatService().get_user_chat_ids(user_id, db)
      for cid in chat_ids:
        await redis_manager.add_user_to_chat(user_id, cid)

  
  async def _send_error(self, user_id: int, text: str):
    await self.send_to_user(user_id, {
      "type": "error",
      "message": text,
      "timestamp": datetime.utcnow().isoformat(),
    })

  
websocket_manager = WebSocketManager()
