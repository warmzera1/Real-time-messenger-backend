import json
import logging 
import asyncio
from typing import Dict, Set 
from datetime import datetime 
from jose import jwt, JWTError

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.database import get_db_session
from app.redis.manager import redis_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class WebSocketManager:
  """
  Упрощенный WebSocket менеджер:
  1. Только управление соединениями
  2. Маршрутизация сообщений
  3. Heartbeat для живых соединений
  """

  def __init__(self):
    # Основные хранилища
    self.active_connections: Dict[int, Set[WebSocket]] = {}     # user_id -> {ws1, ws2}
    self.websocket_to_user: Dict[WebSocket, int] = {}           # ws -> user_id
    self.websocket_data: Dict[WebSocket, dict] = {}             # ws -> user_data 


    # Метрики
    self.metrics = {
        "connections_total": 0,
        "messages_received": 0,
        "messages_sent": 0,
        "errors": 0,
    }

    logger.info("WebSocketManager инициализирован")

    
  async def connect(self, websocket: WebSocket) -> bool:
    """
    Подключение пользователя
    Возвращает True при успехе, False при ошибке
    """

    try:
      session_id = str(id(websocket))

      user_id = await self.authenticate_websocket(websocket)

      # Сохраняем в памяти
      if user_id not in self.active_connections:
          self.active_connections[user_id] = set()
      self.active_connections[user_id].add(websocket)
      self.websocket_to_user[websocket] = user_id
      self.websocket_data[websocket] = {
        "user_id": user_id,
        "session_id": session_id,
      }

      # Отправляем приветственное сообщение
      await self._send_to_websocket(websocket, {
        "type": "connection_established",
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
      })

      # Сообщаем Redis, что пользователь онлайн
      await redis_manager.add_user_session(user_id, session_id)

      # Доставка offline сообщений
      offline_messages = await redis_manager.get_and_clear_offline_messages(user_id)

      for payload in offline_messages:
        await websocket.send_json({
          "type": "chat_message",
          "chat_id": payload["chat_id"],
          "message": payload,
        })

      # Подписываемся на чаты пользователя
      await self._subscribe_to_user_chats(user_id)

      # Метрики
      self.metrics["connections_total"] += 1
      logger.info(
        f"Пользователь {user_id} подключен. Устройств: {len(self.active_connections[user_id])}"
      )

      return True 
    
    except Exception as e:
      logger.error(f"Ошибка подключения: {e}")
      self.metrics["errors"] += 1
      return False 
    

  async def disconnect(self, websocket: WebSocket):
    """Отключение пользователя"""

    try:
      # Получаем user_id или None, если такого websocket уже нет
      user_id = self.websocket_to_user.get(websocket)

      # Если нет user_id, соединение уже удалено ранее, выходим
      if not user_id:
        return
      
      session_id = self.websocket_data.get(websocket, {}).get("session_id")

      # Удаляем websocket из множества подключений пользователя
      if user_id:
        if user_id in self.active_connections:
          self.active_connections[user_id].discard(websocket)

          # Если у пользователя больше нет активных соединений
          if not self.active_connections[user_id]:
            del self.active_connections[user_id]
            # Отписываем от чатов только если это последнее устройство
            await self._unsubscribe_from_user_chats(user_id)

      # Удаляем обратные связи
      if websocket in self.websocket_to_user:
        del self.websocket_to_user[websocket]

      if websocket in self.websocket_data:
        del self.websocket_data[websocket]

      if session_id:
        await redis_manager.remove_user_connection(user_id, session_id)

      if user_id: 
        logger.info(
          f"Пользователь {user_id} отключен. Осталось устройств: {len(self.active_connections.get(user_id, []))}"
        )

    except Exception as e:
      logger.error(f"Ошибка отключения: {e}")
      self.metrics["errors"] += 1

  
  async def handle_incoming_message(self, websocket: WebSocket):
    """
    Основной цикл обработки входящих сообщений
    """

    try:
      while True:
        # Получаем сообщение
        data = await websocket.receive_json()
        self.metrics["messages_received"] += 1

        # Определяем тип сообщения
        message_type = data.get("type")

        if message_type == "chat_message":
          await self._handle_chat_message(websocket, data)
        else:
          logger.warning(f"Неизвестный тип сообщения: {message_type}")
    
    except WebSocketDisconnect:
      logger.info(f"Пользователь {self.websocket_to_user.get(websocket)} отключился")

    except Exception as e:
      logger.error(f"Ошибка обработки сообщения: {e}")
      await self.disconnect(websocket)


  async def handle_incoming_pubsub_message(self, user_id: int, data: dict):
    """
    Отправка сообщения конкретному пользователю через WebSocket
    """

    await self.send_to_user(user_id, {
      "type": "chat_message",
      "data": data,
    })


  async def _handle_chat_message(self, websocket: WebSocket, data: dict):
    """Обработка сообщения чата от клиента"""

    try:
      user_id = self.websocket_to_user.get(websocket)
      if not user_id:
        return 
      
      chat_id = data.get("chat_id")
      content = data.get("content")

      # Валидация
      if not chat_id or not content or len(content.strip()) == 0:
        await self._send_error(websocket, "Неверный формат сообщения")
        return
      
      # Проверка отправителя
      async with get_db_session() as db:
        if not await ChatService().is_user_in_chat(user_id, chat_id, db):
          await self._send_error(websocket, "Не участник чата")
          return 
        
        # Сохраняем в БД
        message = await MessageService().create_message(
          chat_id=chat_id,
          sender_id=user_id,
          content=content.strip(),
          db=db,
        )
        if not message:
          await self._send_error(websocket, "Ошибка сохранения сообщения")
          return 
        
        # Данные для публикаци и оффлайн
        message_data = {
          "id": message.id,
          "chat_id": chat_id,
          "sender_id": user_id,
          "content": content,
          "created_at": message.created_at.isoformat() if message.created_at else None
        }

        # Всегда публикуем один раз - онлайн получат через Pub/Sub
        await redis_manager.publish_chat_message(chat_id, message_data)

        # Оффлайн - сохраняем если получатель не в сети
        members = await ChatService().get_chat_members(chat_id, db)
        for receiver_id in members:
          if receiver_id != user_id:
            if not await redis_manager.is_user_online(receiver_id):
              await redis_manager.store_offline_message(receiver_id, message_data)

    except Exception as e:
      logger.error(f"Ошибка обработки chat_message: {e}")
      self.metrics["errors"] += 1


  async def send_to_user(self, user_id: int, data: dict) -> int:
    """
    Отправка сообщения всем устройствам пользователя
    Возвращает факт доставки сообщения пользователю
    """

    if user_id not in self.active_connections:
      return False 
    
    delivered_count = 0
    dead_connections = []

    for ws in list(self.active_connections[user_id]):
      try:
        await self._send_to_websocket(ws, data)
        delivered_count += 1
        logger.info(f"Доставлено количество сообщений: {delivered_count}")
      except Exception:
        dead_connections.append(ws)

    # Очищаем мертвые соединения
    for ws in dead_connections:
      await self.disconnect(ws)

    return delivered_count
  

  async def _subscribe_to_user_chats(self, user_id: int):
    """Подписать пользователя на всего его чаты"""

    try:
      async with get_db_session() as db:
        chat_ids = await ChatService.get_user_chat_ids(user_id, db)
        for chat_id in chat_ids:
          await redis_manager.subscribe_to_chat(user_id, chat_id)
        logger.debug(f"Пользователь {user_id} подписан на {len(chat_ids)} чатов")
      
    except Exception as e:
      logger.error(f"Ошибка подписки пользователя {user_id} на чаты: {e}")

  
  async def _unsubscribe_from_user_chats(self, user_id: int):
    """Отписать пользователя от всех чатов"""

    try:
      async with get_db_session() as db:
        chat_ids = await ChatService.get_user_chat_ids(user_id, db)
        for chat_id in chat_ids:
          await redis_manager.unsubscribe_from_chat(user_id, chat_id)
        logger.debug(f"Пользователь {user_id} отписан от {len(chat_ids)} чатов")
    
    except Exception as e:
      logger.error(f"Ошибка отписки пользователя {user_id} от чатов: {e}")


  async def authenticate_websocket(self, websocket: WebSocket) -> int:
    """Проверка JWT-токена из query параметра"""

    token = websocket.query_params.get("token")
    if not token:
      await websocket.close(code=1008)
      raise WebSocketDisconnect
    
    try:
      payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
      )

      if payload.get("type") != "access":
        raise JWTError()
      
      user_id = payload.get("sub")
      if not user_id:
        raise JWTError()
      
      return int(user_id)
    
    except JWTError:
      await websocket.close(code=1008)
      raise WebSocketDisconnect


  async def _send_to_websocket(self, websocket: WebSocket, data: dict):
    """Безопасная отправка в WebSocket"""

    try:
      await websocket.send_json(data)
    except Exception as e:
      logger.error(f"Ошибка отправки в WebSocket: {e}")
      raise 


  async def _send_error(self, websocket: WebSocket, message: str):
    """Отправка ошибки клиенту"""

    try:
      await websocket.send_json({
        "type": "error",
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
      })
    
    except Exception:
      pass    # Если не можем отправить ошибку, соединение мертво

  
  def get_stats(self) -> dict:
    """Получить статистику WebSocket-менеджера"""

    total_connections = sum(len(devices) for devices in self.active_connections.values())
    unique_users = len(self.active_connections)

    return {
      **self.metrics,
      "active_connections": total_connections,
      "unique_users_online": unique_users,
      "timestamp": datetime.utcnow().isoformat(),
    }

  
websocket_manager = WebSocketManager()