from fastapi import WebSocket
from typing import Dict, Set
import logging


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

  
  async def disconnect(self, websocket: WebSocket, chat_id: int):
    """
    Отключает WebSocket из чата
    """

    if chat_id in self.active_connections:
      self.active_connections[chat_id].discard(websocket)
      if not self.active_connections[chat_id]:
        del self.active_connections[chat_id]

  
  async def broadcast(self, data: dict, chat_id: int):
    """
    Отправляет сообщение ВСЕМ в чате
    """

    if chat_id not in self.active_connections:
      return 
    
    # Делаем копию, чтобы избежать мутацию во время итерации
    connections = list(self.active_connections[chat_id])
    dead: Set[WebSocket] = set()

    for ws in connections:
      try:
        await ws.send_json(data)
      except Exception as e:
        logger.warning(f"WS error: {e}")
        dead.add(ws)

    # Очищаем мертвые соединения
    for ws in dead:
      self.active_connections[chat_id].discard(ws)


manager = ConnectionManager()
