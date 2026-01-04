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
 



logger = logging.getLogger(__name__)


# class ConnectionManager:
#   """
#   Менеджер WebSocket-соединений
#   Хранит активные соединения по chat_id, позволяет broadcast (отправка всем в чате)
#   """

#   def __init__(self):
#     # chat_id -> set(websocket)
#     self.active_connections: Dict[int, Set[WebSocket]] = {}
#     self.websocket_ids: Dict[WebSocket, str] = {}

  
#   async def connect(self, websocket: WebSocket, chat_id: int, user_id: int):
#     """
#     Подключает WebSocket в нужный чат
#     """

#     # 1. Генерируем уникальный ID для WebSocket
#     ws_id = str(uuid.uuid4())[:8]   # Короткий ID
#     self.websocket_ids[websocket] = ws_id

#     # 2. Локальное хранилище
#     await websocket.accept()
#     if chat_id not in self.active_connections:
#       self.active_connections[chat_id] = set()
#     self.active_connections[chat_id].add(websocket)

#     # 3. Redis: Сохраняем соединение
#     await redis_manager.add_websocket_connection(chat_id, ws_id, user_id)

#     logger.info(f"[connect] Пользователь {user_id} присоединился к чату {chat_id}, ws_id {ws_id}")


#   async def disconnect(self, websocket: WebSocket, chat_id: int):
#     """
#     Отключает WebSocket из чата
#     """
#     try:
#         # Безопасно получаем ID WebSocket (если есть) из локального сервера
#         ws_id = self.websocket_ids.get(websocket)
        
#         # Удаляем WebSocket из словаря всех активных подключений
#         if websocket in self.websocket_ids:
#             del self.websocket_ids[ws_id]
        
#         # Удаляем WebSocket из активных подключений конкретного чата
#         if chat_id in self.active_connections:
#             self.active_connections[chat_id].discard(websocket)
#             # Если в чате нет больше подключений - удаляем чат из словаря
#             if not self.active_connections[chat_id]:
#                 del self.active_connections[chat_id]
        
#         # Удаляем запись из Redis
#         if ws_id:
#             try:
#                 await redis_manager.remove_websocket_connection(chat_id, ws_id)
#             except Exception as e:
#                 logger.error(f"Redis error: {e}")
        
#         logger.info(f"[disconnect] Отключен от чата {chat_id}, ws_id: {ws_id}")
        
#     except Exception as e:
#         logger.error(f"[disconnect] Критическая ошибка: {e}")
#         # Восстановительная очистка: удаляем хотя бы из памяти
#         try:
#             if chat_id in self.active_connections:
#                 self.active_connections[chat_id].discard(websocket)
#         except:
#             pass    # Игнорируем любые ошибки очистки

  
#   async def send_to_all(self, data: dict, chat_id: int):
#     """
#     Отправляет сообщение ВСЕМ в чате
#     """

#     if chat_id not in self.active_connections:
#       logger.warning(f"Нет активных соединений для чата -> {chat_id}")
#       return 
    
#     # Делаем копию, чтобы избежать мутацию во время итерации
#     connections = list(self.active_connections[chat_id])
#     logger.info(f"[send_to_all] Уведомление отправлено в чат {chat_id}, соединений {len(self.active_connections)}, данные: {data}")

#     dead: Set[WebSocket] = set()

#     for ws in connections:
#       try:
#         json_text = json_dumps(data)
#         await ws.send_text(json_text)
#         logger.info(f"[send_to_all] Соединение отправлено в WebSocket")
#       except Exception as e:
#         logger.warning(f"[send_to_all] Ошибка отправки WebSocket: {e}")
#         dead.add(ws)

#     # Очищаем мертвые соединения
#     for ws in dead:
#       if chat_id in self.active_connections:
#         self.active_connections[chat_id].discard(ws)
#     logger.info(f"[send_to_all] Удалено: {len(dead)} мертвых соединений")


#   async def send_to_other(self, data: dict, chat_id: int, exclude_ws: WebSocket):
#       """Отправляет ВСЕМ кроме указанного соединения"""

#       # 1. Проверяем, есть ли активные соединения в чате  
#       if chat_id not in self.active_connections:
#         logger.warning(f"[send_to_other] Нет активных соединений в чате: {chat_id}")
#         return
      
#       # 2. Фильтрация соединений, если нет - ошибка
#       connections = [
#         ws for ws in self.active_connections[chat_id]
#         if ws != exclude_ws
#       ]
#       logger.info(f"[send_to_other] Будет отправлено {len(connections)} получателям")
      
#       if not connections:
#         logger.info(f"[send_to_other] Нет получателей для отправки")
#         return 
      
#       # 3. Сериализация данных
#       try:
#         json_text = json_dumps(data)
#       except Exception as e:
#         logger.error(f"[send_to_other] Ошибка сериализации: {e}")
#         return 
      

#       for ws in connections:
#         try:
#           await ws.send_text(json_text)
#           logger.debug(f"[send_to_other] Успешно отправлено")
#         except Exception as e:
#           logger.error(f"[send_to_other] Ошибка отправителя: {e}")

#       logger.info(
#         f"[send_to_other] Завершено"
#       )  



# manager = ConnectionManager()



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


  async def connect(self, websocket: WebSocket, user: User): 
    """
    Подключение пользователя по WebSocket

    Args:
      websocket: WebSocket соединение
      user: Авторизованный пользователь
    """

    try:
      # 1. Уникальный ID соединения
      ws_id = str(uuid.uuid())[:8]
      self.websocket_ids[websocket] = ws_id

      # 2. Принимаем соединение
      await websocket.accept()

      # 3. Сохраняем в локальное хранилище
      user_id = user.id 
      if user_id not in self.active_connections:
        self.active_connections[user_id] = set()
      self.active_connections[user_id].add(websocket)
      self.websocket_to_user[websocket] = user_id

      # 4. Регистрируем в Redis
      await redis_manager.register_user_connections(
        user_id=user_id,
        ws_id=ws_id,
        server_id="main",
      )

      # 5. Подписываемся на события пользователя
      await self._subscribe_to_user_events(user_id)

      # 6. Запускаем heartbeat
      self.heartbeat_tasks[websocket] = asyncio.create_task(
        self._heartbeat(websocket)
      )

      logger.info(f"[WS Connect] Пользователь {user_id} присоединился, ws_id: {ws_id}")

      # 7. Отправляем приветственное сообщение
      await self.send_personal({
        "type": "connection_established",
        "message": "WebSocket подключен успешно",
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
      }, websocket)

    except Exception as e:
      logger.error(f"[WS Connect] Error: {e}")
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
    user_chats = await self._get_user_chats(user_id)

    # Подписываемся на каналы
    for chat_id in user_chats:
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

    pass 

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
    """

    pass 


  async def _get_chat_members(self, chat_id: int) -> List[int]:
    """
    Получение участников чата
    """

    pass 


websocket_manager = WebSocketManager()