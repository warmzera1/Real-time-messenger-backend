import json
import logging 
import asyncio
from typing import Dict, Set 
from datetime import datetime 

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.services.delivery_service import DeliveryService
from app.services.read_service import ReadService
from app.services.chat_read_service import ChatReadService
from app.database import AsyncSessionLocal
from app.database import get_db_session
from app.redis.manager import redis_manager 

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

    # Для heartbeat
    self.heartbeat_tasks: Dict[WebSocket, asyncio.Task] = {}

    # Метрики
    self.metrics = {
        "connections_total": 0,
        "messages_received": 0,
        "messages_sent": 0,
        "errors": 0,
    }

    logger.info("WebSocketManager инициализирован")

    
  async def connect(self, websocket: WebSocket, user_data: dict) -> bool:
    """
    Подключение пользователя
    Возвращает True при успехе, False при ошибке
    """

    try:
      user_id = user_data["id"]

      session_id = str(id(websocket))

      # # Принимаем соединение
      # await websocket.accept()

      # Сохраняем в памяти
      if user_id not in self.active_connections:
          self.active_connections[user_id] = set()
      self.active_connections[user_id].add(websocket)
      self.websocket_to_user[websocket] = user_id
      self.websocket_data[websocket] = {
        **user_data,
        "session_id": session_id,
      }

      # Сообщаем Redis, что пользователь онлайн
      await redis_manager.add_user_session(user_id, session_id)

      # Подписываемся на чаты пользователя
      await self._subscribe_to_user_chats(user_id)

      # # Запускаем heartbeat
      # self.heartbeat_tasks[websocket] = asyncio.create_task(
      #   self._heartbeat(websocket)
      # )

      # Отправляем приветственное сообщение
      await self._send_to_websocket(websocket, {
        "type": "connection_established",
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
      })

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

      # Останавливаем и удаляем задачу heartbeat
      if websocket in self.heartbeat_tasks:
        task = self.heartbeat_tasks.pop(websocket)
        task.cancel()

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
        elif message_type == "pong":
          continue    # Игнориурем PONG, heartbeat обрабатывает
        elif message_type == "ack":
          await self._handle_chat_read_ask(websocket, data)
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

    delivered = await self.send_to_user(user_id, {
      "type": "chat_message",
      "data": data,
    })

    # Если доставка прошла успешно (хоть одному устройству)
    if delivered:
      # Отмечаем сообщение как "доставленное" в базе
      await DeliveryService.mark_delivered(
        message_id=data["id"],
        recipient_id=user_id,
      )


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
      
      # Проверяем, состоимт ли пользователь в чате
      async with get_db_session() as db:
        is_member = await ChatService().is_user_in_chat(user_id, chat_id, db)
        if not is_member:
          await self._send_error(websocket, "Не является участником чата")
          return
      
        # Сохраняем в БД
        message_service = MessageService()
        message = await message_service.create_message(
          chat_id=chat_id,
          sender_id=user_id,
          content=content.strip(),
          db=db,
        )

        if not message:
          await self._send_error(websocket, "Ошибка при сохранении сообщения")
          return 
        
        # Публикуем в Redis
        message_data = {
          "id": message.id,
          "chat_id": chat_id,
          "sender_id": user_id,
          "content": content,
          "created_at": message.created_at.isoformat() if message.created_at else None,
          "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
        }

        await redis_manager.publish_chat_message(chat_id, message_data)
        logger.debug(f"Сообщение {message.id} опубликовано в чате {chat_id}")

    except Exception as e:
      logger.error(f"Ошибка обработки chat_message: {e}")
      self.metrics["errors"] += 1


  async def _handle_chat_read_ask(self, websocket: WebSocket, data: dict):
    """
    Обрабатывает клиентские события 'я прочитал чат до сообщенич Х'
    """

    user_id = self.websocket_to_user.get(websocket)
    if not user_id:
      logger.warning("ACK без user_id")
      return 
    
    chat_id = data.get("chat_id")
    last_read_message_id = data.get("last_read_message_id")

    if not chat_id or not last_read_message_id:
      logger.warning("Невалидный ACK payload", data)
      return 
    
    async with get_db_session() as db:
      await ChatReadService().mark_chat_read(
        chat_id=chat_id,
        user_id=user_id,
        last_read_message_id=last_read_message_id,
        db=db,
      )



  async def send_to_user(self, user_id: int, data: dict) -> bool:
    """
    Отправка сообщения всем устройствам пользователя
    Возвращает факт доставки сообщения пользователю
    """

    if user_id not in self.active_connections:
      return False 
    
    delivered = False
    dead_connections = []

    for ws in list(self.active_connections[user_id]):
      try:
        await self._send_to_websocket(ws, data)
        delivered = True
        logger.info("Сообщение доставлено: {delivered}")
      except Exception:
        dead_connections.append(ws)

    # Очищаем мертвые соединения
    for ws in dead_connections:
      await self.disconnect(ws)

    return delivered
  

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


  # async def _heartbeat(self, websocket: WebSocket):
  #   """Поддержание живого соединения"""

  #   try:
  #     while True:
  #       await asyncio.sleep(25)   # Отправляем каждые 25 секунд

  #       try:
  #         await websocket.send_json({
  #           "type": "ping"
  #         })

  #         # Ждем PONG 5 секунд
  #         response = await asyncio.wait_for(
  #           websocket.receive_json(),
  #           timeout=5,
  #         )

  #         if response.get("type") != "pong":
  #           logger.warning("Некорректный ответ на PING")
  #           break

  #       except asyncio.TimeoutError:
  #         logger.warning("Timeout heartbeat, отключаем")
  #         break
  #       except Exception as e:
  #         logger.error(f"Ошибка hearbeat: {e}")
  #         break

  #   except asyncio.CancelledError:
  #     logger.debug("Heartbeat task отменен")
  #   except Exception as e:
  #     logger.error(f"Неожиданная ошибка hearbeat: {e}")
  #   finally:
  #     await self.disconnect(websocket)


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
    """Получить статистику WebSocket-менеджераxn"""

    total_connections = sum(len(devices) for devices in self.active_connections.values())
    unique_users = len(self.active_connections)

    return {
      **self.metrics,
      "active_connections": total_connections,
      "unique_users_online": unique_users,
      "timestamp": datetime.utcnow().isoformat(),
    }

  
websocket_manager = WebSocketManager()