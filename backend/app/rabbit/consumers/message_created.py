import json 
from app.websocket.manager import websocket_manager
from app.redis.manager import redis_manager
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.database import get_db_session 


class MessageCreatedConsumer:
  """
  Обработчик события 'сообщение создано'
  """

  def __init__(self):
    self.chat_service = ChatService()

  
  async def handle(self, payload: dict):
    """
    Обрабатывает событие message.created
    """

    chat_id = payload["chat_id"]
    sender_id = payload["sender_id"]

    # 1. Получаем участников чата
    async with get_db_session() as db:
      user_ids = await self.chat_service.get_chat_members(chat_id, db)

    # 2. Рассылаем сообщение
    for user_id in user_ids:
      if user_id == sender_id:
        continue 

      if await redis_manager.is_user_online(user_id):
        await websocket_manager.send_to_user(
          user_id=user_id,
          data={
            "type": "chat_message",
            "chat_id": chat_id,
            "message": payload,
          },
        )
      else:
        await redis_manager.store_offline_message(
          user_id=user_id,
          payload=payload,
        )
