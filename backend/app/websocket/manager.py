from fastapi import WebSocket
from typing import Dict, Set


class ConnectionManager:
  """
  Менеджер WebSocket-соединений
  Хранит активные соединения по chat_id, позволяет broadcast (отправка всем в чате)
  """

  def __init__(self):
    # chat_id = set(WebSocket)
    self.active_connections: Dict[int, Set[WebSocket]] = {}

  
  async def connection(self, websocket: WebSocket, chat_id: int):
    """
    Подключает WebSocket в нужный чат
    """

    await websocket.accept()
    if chat_id not in self.active_connections:
      self.active_connections[chat_id] = set()
    self.active_connections[chat_id].add(websocket)

  
  def disconnect(self, websocket: WebSocket, chat_id: int):
    """
    Отключает WebSocket из чата
    """

    if chat_id in self.active_connections:
      self.active_connections[chat_id].discard(websocket)
      if not self.active_connections[chat_id]:
        del self.active_connections[chat_id]

  
  async def broadcast(self, message: dict, chat_id: int):
    """
    Отправляет сообщение ВСЕМ в чате
    """

    if chat_id in self.active_connections:
      for connection in self.active_connections[chat_id]:
        await connection.send_json(message)


manager = ConnectionManager()
