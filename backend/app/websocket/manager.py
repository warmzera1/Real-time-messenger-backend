import json
import uuid
import asyncio
from fastapi import WebSocket
from typing import Dict, Set, List, Optional
from datetime import datetime
import logging

from app.utils.json_encoder import json_dumps
from app.redis.manager import redis_manager
from app.models.user import User
from app.services.chat_services import ChatService



logger = logging.getLogger(__name__)


class WebSocketManager:
  """
  Универсальный WebSocket менеджер для пользовательских событий
  Поддерживает:
  - Новые сообщения из всех чатов пользователя
  - Обновления настроек чатов и пользователей
  - Системные уведомления
  """

  def __init__(self):
    # Основное хранилище user_id -> set(websocket соединение)
    # У пользователя может быть несколько соединений (разные устройства)
    self.active_connections: Dict[int, Set[WebSocket]] = {}

    # Обратная связь: websocket -> user_id
    self.websocket_to_user: Dict[WebSocket, int] = {}

    # Уникальный ID для каждого соединения
    self.websocket_ids: Dict[WebSocket, str] = {}

    # Храним таски для heartbeat 
    self.heartbeat_tasks: Dict[WebSocket, asyncio.Task] = {}

    # Для полных данных пользователя
    self.user_data_by_ws: Dict[WebSocket, dict] = {}

    # Чат-сервис
    self.chat_service = ChatService()


  async def connect(self, websocket: WebSocket, user_data: dict): 
    """
    Подключение пользователя по WebSocket

    Args:
      websocket: WebSocket соединение
      user_data: {"id": 1, "username": "user", "email": "user@example.com"}
    """

    try:
      # 1. Извлекаем user_id из словаря
      user_id = user_data["id"]

      # 2. Уникальный ID соединения
      ws_id = str(uuid.uuid4())[:8]
      
      # 3. Сохраняем маппинги
      self.websocket_ids[websocket] = ws_id
      self.user_data_by_ws[websocket] = user_data

      # 4. Принимаем соединение
      await websocket.accept()

      # 5. Сохраняем в локальное хранилище
      if user_id not in self.active_connections:
        self.active_connections[user_id] = set()
      self.active_connections[user_id].add(websocket)
      self.websocket_to_user[websocket] = user_id

      # 6. Регистрируем в Redis
      await redis_manager.register_user_connections(
        user_id=user_id,
        ws_id=ws_id,
        server_id="main",
      )

      # 7. Подписываемся на события пользователя
      await self._subscribe_to_user_events(user_id)

      # 8. Запускаем heartbeat
      self.heartbeat_tasks[websocket] = asyncio.create_task(
        self._heartbeat(websocket)
      )

      logger.info(f"[WS Connect] Пользователь {user_id} ({user_data['username']}) присоединился, ws_id: {ws_id}")

      # 9. Отправляем приветственное сообщение
      await self.send_personal({
        "type": "connection_established",
        "message": "WebSocket подключен успешно",
        "user": user_data,
        "timestamp": datetime.utcnow().isoformat()
      }, websocket)

    except Exception as e:
      logger.error(f"[WS Connect] Ошибка: {e}")
      raise

  async def disconnect(self, websocket: WebSocket):
    """
    Отключение WebSocket соединения
    """

    try:
      # 1. Получаем user_id и ws_id
      user_id = self.websocket_to_user.get(websocket)
      ws_id = self.websocket_ids.get(websocket)

      # 2. Останавливаем heartbeat
      if websocket in self.heartbeat_tasks:
        task = self.heartbeat_tasks.pop(websocket)
        task.cancel()
        try: 
          await task
        except asyncio.CancelledError:
          pass 

      # 3. Удаляем из локального хранилища
      if user_id is not None and user_id in self.active_connections:
        self.active_connections[user_id].discard(websocket)
        if not self.active_connections[user_id]:
          del self.active_connections[user_id]

      if websocket in self.websocket_to_user:
        del self.websocket_to_user[websocket]

      if websocket in self.websocket_ids:
        del self.websocket_ids[websocket]

      # 4. Удаляем из Radis
      if user_id and ws_id:
        await redis_manager.unregister_user_connection(
          user_id=user_id,
          ws_id=ws_id,
        )

      logger.info(f"[WS Disconnect] Пользователь {user_id} отключился, ws_id: {ws_id}")

    except Exception as e:
      logger.error(f"[WS Disconnect] Ошибка: {e}")


  async def _subscribe_to_user_events(self, user_id: int):
    """
    Подписка на все события пользователя Redis

    Включает: 
    - Сообщения из всех чатов пользователя
    - Обновления профиля
    - Уведомления
    """

    # Получаем все чаты пользователя
    chat_service = ChatService()

    chats = await chat_service.get_user_chat_ids(user_id)
    chat_ids = [chat.id for chat in chats]

    logger.info(f"[Subscribe] Пользователь {user_id} имеет количество {len(chat_ids)} чатов")

    # Подписываемся на каналы
    for chat_id in chat_ids:
      # Канал новых сообщений
      await redis_manager.subscribe_to_chat_messages(user_id, chat_id)
      # Канал обновлений чата
      await redis_manager.subscribe_to_chat_updates(user_id, chat_id)

    # Подписываемся на обновления профиля
    await redis_manager.subscribe_to_user_updates(user_id)

    # Подписываемся на системные уведомления
    await redis_manager.subscribe_to_notifications(user_id)

  async def _get_user_chats(self, user_id: int) -> List[int]:
    """
    Получение списка чатов пользователя
    """

    try:
      # Получаем чаты пользователей через сервис
      chats = await self.chat_service.get_user_chats(user_id)

      # Извлекаем только ID чатов
      chat_ids = [chat.id for chat in chats]

      logger.debug(f"[Get User Chats] Пользователь {user_id} имеет чаты: {chat_ids}")
      return chat_ids
    
    except Exception as e:
      logger.error(f"[Get User Chats] Ошибка для пользователя: {user_id}: {e}")
      return []   # Возвращаем пустой список при ошибке


  async def _heartbeat(self, websocket: WebSocket):
    """
    Поддержание соединения через ping-pong
    """    

    try:
      while True:
        await asyncio.sleep(30)   # Каждые 30 секунд
        try:
          await websocket.send_json({
            "type": "ping"
          })
          # Ждем pong 5 секунд
          response = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=5,
          )
          if response.get("type") != "pong":
            logger.warning(f"Heartbeat невалидный ответ: {response}")
            break 

        except asyncio.TimeoutError:
          logger.warning(f"Hearbeat timeout, отключение")
          break 
        except Exception as e:
          logger.error(f"Heartbeat ошибка: {e}")
          break 

    except asyncio.CancelledError:
      logger.info("Heartbeat task отменена")
    finally:
      await self.disconnect(websocket)


  async def send_personal(self, data: dict, websocket: WebSocket):
    """
    Отправка сообщений конкретному соединению
    """

    try:
      json_text = json_dumps(data)
      await websocket.send_text(json_text)
      logger.debug(f"[Personal] Отправка пользователю: {self.websocket_to_user.get(websocket)}")
    except Exception as e:
      logger.error(f"[Personal] Отправка ошибки: {e}")
      await self.disconnect(websocket)


  async def send_to_user(self, user_id: int, data: dict):
    """
    Отправка сообщения всем соединениям пользователя
    (все ЕГО устройства получат сообщение)
    """

    if user_id not in self.active_connections:
      logger.warning(f"[To User] Нет активных соединений у пользователя: {user_id}")

    dead_connections = set()
    connections = list(self.active_connections[user_id])

    json_text = json_dumps(data)

    for ws in connections:
      try:
        await ws.send_text(json_text)
        logger.debug(f"[To User] Отправить сообщение пользователю: {user_id}")
      except Exception as e:
        logger.error(f"[To User] Ошибка отправки: {e}")
        dead_connections.add(ws)

    # Чистим мертвые соединения
    for ws in dead_connections:
      await self.disconnect(ws) 


  async def broadcast(self, data: dict, exclude_user_id: Optional[int] = None):
    """
    Широковещательная рассылка всем пользователям
    """

    dead_connections = set()

    json_text = json_dumps(data)

    for user_id, connections in self.active_connections.items():
      if exclude_user_id and user_id == exclude_user_id:
        continue 

      for ws in list(connections):
        try:
          await ws.send_text(json_text)
        except Exception as e:
          logger.error(f"[Broadcast] Ошибка: {e}")
          dead_connections.add(ws)

    for ws in dead_connections:
      await self.disconnect(ws)

    
  async def handle_incoming_message(self, websocket: WebSocket):
    """
    Обработка входящих сообщений от клиента
    """

    try:
      while True:
        # Читаем сообщения от клиента
        data = await websocket.receive_json()

        user_id = self.websocket_to_user.get(websocket)
        if not user_id:
          logger.warning("Сообщение от неавторизованного ответа")
          await self.disconnect(websocket)
          break 

        message_type = data.get("type")

        if message_type == "pong":
          # Обработка heartbeat
          continue 
        elif message_type == "typing":
          # Пользователь печатает
          chat_id = data.get("chat_id")
          await self._handle_typing(user_id, chat_id)
        elif message_type == "read_receipt":
          # Прочитано сообщение
          message_id = data.get("message_id")
          await self._handle_read_receipt(user_id, message_id)
        else:
          logger.warning(f"Сообщение неизвестного типа: {message_type}")

    except Exception as e:
      logger.error(f"[Handle Message] Ошибка: {e}")
      await self.disconnect(websocket)


  async def _handle_typing(self, user_id: int, chat_id: int):
    """
    Рассылка уведомления "пользователь печатает"
    """

    # Получаем всех участников чата, кроме отправителя
    chat_members = await self._get_chat_members(chat_id)

    for member_id in chat_members:
      if member_id != user_id:
        await self.send_to_user(member_id, {
          "type": "user_typing",
          "chat_id": chat_id,
          "user_id": user_id,
          "timestamp": datetime.utcnow().isoformat()
        })


  async def _handle_read_receipt(self, user_id: int, message_id: int):
    """
    Обработка прочтения сообщения

    Логика:
    1. Помечаем сообщение как прочитанное из БД
    2. Получаем отправителя сообщения
    3. Отправляем отправителю уведомление о прочтении
    """

    try:
      from app.services.message_service import MessageService
      message_service = MessageService()

      # 1. Помечаем сообщение как прочитанное
      marked = await message_service.mark_as_read(message_id, user_id)

      if not marked:
        # Сообщение уже прочитано
        logger.debug(f"Сообщение {message_id} УЖЕ прочитано пользователем: {user_id}")
        return 
      
      # 2. Получаем информацию о сообщение 
      message_info = await message_service.get_message_info(message_id)

      if not message_info:
        logger.error(f"Сообщение {message_id} не найдено")
        return 
      
      sender_id = message_info["sender_id"]
      chat_id = message_info["chat_id"]

      # 3. Отправляем уведомление отправителю (если он онлайн)
      if sender_id != user_id:    # Не отправляем себе
        await self.send_to_user(
          sender_id, {
            "type": "message_read",
            "message_id": message_id,
            "chat_id": chat_id, 
            "reader_id": user_id,
            "read_at": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().isoformat(),
          }
        )

        logger.info(f"Уведомление о прочтении отправителю: сообщение {message_id}, "
                    f"Читатель {user_id}, отправитель {sender_id}")
        
        # 4. Отправляем ВСЕМ в чате уведомдление (опционально)
        # Например, для групповых чатов
        await self._notify_chat_about_read(chat_id, message_id, user_id)

    except Exception as e:
      logger.error(f"[Handle Read Receipt] Ошибка: {e}")

  
  async def _notify_chat_about_read(
      self,
      chat_id: int,
      message_id: int,
      user_id: int,
  ):
    """
    Уведомление участников чата о прочтении сообщения
    (только для чатов с 2+ участников)
    """

    try:
      # Получаем участников чата
      chat_service = ChatService()

      members = await chat_service.get_chat_members(chat_id)

      if len(members) <= 2:
        # Для личных чатов не уведомляем всех
        return 
      
      # Уведомляем всех, кроме прочитавших
      for member_id in members:
        if member_id != user_id:
          await self.send_to_user(
            member_id, {
              "type": "message_read_in_chat",
              "message_id": message_id,
              "chat_id": chat_id,
              "reader_id": user_id,
              "timestamp": datetime.utcnow().isoformat()
            }
          )

    except Exception as e:
      logger.error(f"[Notify Chat Read] Ошибка: {e}")


  async def _get_chat_members(self, chat_id: int) -> List[int]:
    """
    Получение участников чата через ChatService
    """

    try:
      chat_service = ChatService()

      return await chat_service.get_user_chats(chat_id)

    except Exception as e:
      logger.error(f"[Get Chat Members] Ошибка чата: {chat_id}: {e}")
      return []


websocket_manager = WebSocketManager()