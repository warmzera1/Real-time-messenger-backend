import logging 
import asyncio

from datetime import datetime 

from fastapi import WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from app.core.config import settings 
from app.redis.manager import redis_manager
from app.services.chat_service import ChatService 
from app.services.message_service import MessageService
from app.database import get_db_session

logger = logging.getLogger(__name__)


class AuthHandler:
  """Аутентификация WebSocket"""

  async def authenticate(self, ws: WebSocket) -> int | None:
    token = ws.headers.get("authorization")
    if not token or not token.startswith("Bearer "):
      await ws.close(code=1008)
      return None 

    token = token[7:].strip()
    try:
      payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
      )
      return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
      await ws.close(code=1008)
      return None 
    

class ConnectionManager:
  """Онлайн-соединения, connect/disconnect"""

  def __init__(
    self, 
    auth_handler: AuthHandler,
    membership_sync: "ChatMembershipSync",
  ):
    self.auth_handler = auth_handler
    self.membership_sync = membership_sync
    self.connections: dict[int, WebSocket] = {}


  async def connect(self, ws: WebSocket) -> int | None : 
    """
    Подключение и отмечаем пользователя онлайн
    """

    try:
      user_id = await self.auth_handler.authenticate(ws)
      if user_id is None:
        return None  

      if user_id in self.connections:
        await self.connections[user_id].close(code=1000)

      self.connections[user_id] = ws 

      await self.membership_sync.sync_chat_memberships(user_id)

      await redis_manager.mark_user_online(user_id)

      await ws.send_json({
        "type": "connected",
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
      })

      logger.info(f"Пользователь {user_id} подключен")

      return user_id

    except Exception as e:
      logger.warning(f"Подключение неудалось: {e}")
      await ws.close(code=1008) 
      return None 
    
  
  async def disconnect(self, ws: WebSocket):
    """
    Удаляем соединение и отмечаем пользователя оффлайн
    """

    user_id = self.find_user_by_ws(ws)
    if user_id is None:
      return 
    
    self.connections.pop(user_id, None)
    await redis_manager.mark_user_offline(user_id)

    try:
      await ws.close(code=1000)
    except Exception:
      pass

  
  def find_user_by_ws(self, ws: WebSocket) -> int | None:
    for uid, active in self.connections.items():
      if active == ws:
        return uid 
    return None 

  
  async def send_to_user(self, user_id: int, payload: dict) -> bool:
    """
    Отправляет данные конкретному пользователю, если он онлайн
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
  

  async def send_error(self, user_id: int, text: str):
    await self.send_to_user(user_id, {
      "type": "error",
      "message": text,
      "timestamp": datetime.utcnow().isoformat(),
    })
    

class MessageHandler():
  """Обработка входящих WS-сообщений"""

  def __init__(
    self, 
    connection_manager: ConnectionManager,
    delivery_manager: "DeliveryManager",
  ):
    self.connection_manager = connection_manager
    self.delivery_manager = delivery_manager
  
    
  async def receive_loop(self, ws: WebSocket):
    """
    Основной цикл чтения сообщения от клиента 
    с проверкой активности соединения
    """

    user_id = self.connection_manager.find_user_by_ws(ws)
    if user_id is None:
      await ws.close()
      return 
    
    missed = 0
    max_missed = 3
    ping_interval_sec = 25
    
    try:
      while True:
        try:
          data = await asyncio.wait_for(
            ws.receive_json(), 
            timeout=ping_interval_sec
          )

          msg_type = data.get("type")

          if msg_type == "pong":
            missed = 0
          elif msg_type == "message":
            await self.handle_user_message(user_id, data)
          elif msg_type == "read":
            await self.handle_read_message(user_id, data)
          elif msg_type == "edit_message":
            await self.handle_edit_message(user_id, data)
          else:
            logger.debug(f"Неизвестный тип сообщения: {msg_type}")

        except asyncio.TimeoutError:
            await ws.send_json({"type": "ping"})
            missed += 1
            if missed >= max_missed:
              await self.connection_manager.disconnect(ws)
              break 

    except WebSocketDisconnect:
      await self.connection_manager.disconnect(ws)
    except Exception as e:
      logger.error(f"Ошибка в receive loop: {e}")
      await self.connection_manager.disconnect(ws)


  async def handle_user_message(self, user_id: int, data: dict):
    """
    Обрабатывает сообщение от пользователя
    """

    if not await redis_manager.rate_limiting_check(user_id):
        await self.connection_manager.send_error(
          user_id, 
          "Слишком много сообщений. Подождите 10 секунд"
        )
        return

    chat_id = data.get("chat_id")
    content = (data.get("content") or "").strip()

    if not chat_id or not content:
      await self.connection_manager.send_error(
        user_id, 
        "Требуется указать chat_id и непустое содержимое текста"
      )
      return

    async with get_db_session() as db:
      if not await ChatService.is_user_in_chat(user_id, chat_id, db):
        await self.connection_manager.send_error(
          user_id, 
          "Вы не являетесь участников чата"
        )
        return 
      
      msg = await MessageService.create_message(
        chat_id=chat_id,
        sender_id=user_id,
        content=content,
        db=db,
      )
      if not msg:
        await self.connection_manager.send_error(
          user_id, 
          "Ошибка при сохранении сообщения"
        )
        return

      message = {
        "id": msg.id,
        "chat_id": chat_id,
        "sender_id": user_id,
        "content": content,
        "created_at": msg.created_at.isoformat(),
      }

      await redis_manager.publish_to_chat(chat_id, message) 


  async def handle_read_message(self, user_id: int, data: dict):
    """
    Обработка отметки сообщений как прочитанных (батчинг)
    """

    message_ids = data.get("message_ids", [])
    if not message_ids:
      return 
    
    message_ids = [mid for mid in message_ids if isinstance(mid, int)]
    if not message_ids:
      return 
    
    async with get_db_session() as db:
      updated = await MessageService.mark_messages_as_read(
        message_ids=message_ids,
        reader_id=user_id,
        db=db,
      )
      logger.debug(f"Прочитано {updated} сообщений для пользователя {user_id}")


  async def handle_edit_message(self, user_id: int, data: dict):
    """
    Обработка события 'сообщение отредактировано' участником чата
    """

    message_id = data.get("message_id")
    new_content = data.get("content")
    chat_id = data.get("chat_id")

    if not message_id or not new_content:
      return 
  
    async with get_db_session() as db:
      success = await MessageService.edit_message(
        message_id=message_id,
        user_id=user_id,
        new_content=new_content,
        db=db,
      )
      if success:
        await self.delivery_manager.broadcast_to_chat(
          chat_id=chat_id,
          message={
            "type": "message_edited",
            "message_id": message_id,
            "new_content": new_content,
            "edited_at": datetime.utcnow().isoformat(),
          }
        ) 


class DeliveryManager():
  """
  Доставка сообщений (online/offline)
  """

  def __init__(self, connection_manager: ConnectionManager):
    self.connections_manager = connection_manager

  async def broadcast_to_chat(self, chat_id: int, message: dict):
    """
    Рассылает сообщение всем онлайн-участникам чата (кроме отправителя)
    Для определения участников используем Redis set - chat_members:{chat_id}
    """

    members_key = f"chat_members:{chat_id}"
    member_ids = await redis_manager.redis.smembers(members_key)
    if not member_ids:
      return 

    async with get_db_session() as db:

      for raw_id in member_ids:
        try:
          user_id = int(raw_id)
        except ValueError:
          continue 
        
        sent = await self.connections_manager.send_to_user(user_id, message)
        
        if sent:
          if "id" in message:
            await MessageService.mark_delivered(
              message_id=message["id"],
              user_id=user_id,
              db=db,
            )
        else:
          await redis_manager.store_offline_message(user_id, message)


  async def send_pending_messages(self, user_id: int, ws: WebSocket):
    """
    Рассылает сообщение, когда пользователь подключается
    """

    async with get_db_session() as db:
      messages = await redis_manager.get_and_remove_offline_messages(user_id)
      for msg in messages:
        await ws.send_json(msg)
        await MessageService.mark_delivered(
          message_id=msg["id"], 
          user_id=user_id, 
          db=db
        )


class ChatMembershipSync:
  """
  Синхронизация чатов пользователя
  """

  async def sync_chat_memberships(self, user_id: int):
    async with get_db_session() as db:
      chat_ids = await ChatService().get_user_chat_ids(user_id, db)
      for cid in chat_ids:
        await redis_manager.add_user_to_chat(user_id, cid)


class WebSocketManager:
  """
  Composition Root
  """

  def __init__(self):
    self.auth_handler = AuthHandler()
    self.membership_sync = ChatMembershipSync()

    self.connection_manager = ConnectionManager(
      auth_handler=self.auth_handler,
      membership_sync=self.membership_sync,
    )

    self.delivery_manager = DeliveryManager(
      connection_manager=self.connection_manager
    )

    self.message_handler = MessageHandler(
      connection_manager=self.connection_manager,
      delivery_manager=self.delivery_manager
    )


websocket_manager = WebSocketManager()
