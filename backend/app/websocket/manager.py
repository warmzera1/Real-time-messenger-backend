import json
from fastapi import WebSocket
from typing import Dict, Set
import logging

from app.utils.json_encoder import json_dumps



logger = logging.getLogger(__name__)


class ConnectionManager:
  """
  Менеджер WebSocket-соединений
  Хранит активные соединения по chat_id, позволяет broadcast (отправка всем в чате)
  """

  def __init__(self):
    # chat_id -> set(websocket)
    self.active_connections: Dict[int, Set[WebSocket]] = {}

  
  async def connect(self, websocket: WebSocket, chat_id: int):
    """
    Подключает WebSocket в нужный чат
    """

    await websocket.accept()
    if chat_id not in self.active_connections:
      self.active_connections[chat_id] = set()
    self.active_connections[chat_id].add(websocket)
    logger.info(f"Пользователь подключился к чату: {chat_id}. Всего соединений -> {len(self.active_connections.get(chat_id, []))}")

  
  async def disconnect(self, websocket: WebSocket, chat_id: int):
    """
    Отключает WebSocket из чата
    """

    if chat_id in self.active_connections:
      self.active_connections[chat_id].discard(websocket)
      if not self.active_connections[chat_id]:
        del self.active_connections[chat_id]
    logger.info(f"Пользователь отключился от чата -> {chat_id}")

  
  async def send_to_all(self, data: dict, chat_id: int):
    """
    Отправляет сообщение ВСЕМ в чате
    """

    if chat_id not in self.active_connections:
      logger.warning(f"Нет активных соединений для чата -> {chat_id}")
      return 
    
    # Делаем копию, чтобы избежать мутацию во время итерации
    connections = list(self.active_connections[chat_id])
    logger.info(f"Broadcast в чат {chat_id}, соединений {len(self.active_connections)}, данные: {data}")

    dead: Set[WebSocket] = set()

    for ws in connections:
      try:
        json_text = json_dumps(data)
        await ws.send_text(json_text)
        logger.info(f"Соединение отправлено в WebSocket")
      except Exception as e:
        logger.warning(f"Ошибка отправки WebSocket: {e}")
        dead.add(ws)

    # Очищаем мертвые соединения
    for ws in dead:
      if chat_id is self.active_connections:
        self.active_connections[chat_id].discard(ws)
    logger.info(f"Удалено: {len(dead)} мертвых соединений")


  async def send_to_other(self, data: dict, chat_id: int, exclude_ws: WebSocket):
      """Отправляет ВСЕМ кроме указанного соединения"""

      # 1. Проверяем, есть ли активные соединения в чате  
      if chat_id not in self.active_connections:
        logger.warning(f"[send_to_other] Нет активных соединений в чате: {chat_id}")
        return
      
      # 2. Фильтрация соединений, если нет - ошибка
      connections = [
        ws for ws in self.active_connections[chat_id]
        if ws != exclude_ws
      ]
      logger.info(f"[send_to_other] Будет отправлено {len(connections)} получателям")
      
      if not connections:
        logger.info(f"[send_to_other] Нет получателей для отправки")
        return 
      
      # 3. Сериализация данных
      try:
        json_text = json_dumps(data)
      except Exception as e:
        logger.error(f"[send_to_other] Ошибка сериализации: {e}")
        return 
      

      for ws in connections:
        try:
          await ws.send_text(json_text)
          logger.debug(f"[send_to_other] Успешно отправлено")
        except Exception as e:
          logger.error(f"[send_to_other] Ошибка отправителя: {e}")

      logger.info(
        f"[send_to_other] Завершено: "
      )  



manager = ConnectionManager()


