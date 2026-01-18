from app.services.chat_read_service import ChatReadService 
from app.services.chat_service import ChatService
from app.websocket.manager import websocket_manager
from app.database import get_db_session


class ChatReadConsumer:

  async def handle(self, payload: dict):
    """
    Обработка события 'сообщение прочитано'
    """

    chat_id = payload["chat_id"]                                  # Берем ID чата
    user_id = payload["user_id"]                                  # Кто прочитал
    last_read_message_id = payload["last_read_message_id"]        # До какого сообщения

    async with get_db_session() as db:                            # Открываем транзакцию
      await ChatReadService.mark_chat_read(                       # Сохраняем в БД факт прочтения
        chat_id=chat_id,
        user_id=user_id,
        last_read_message_id=last_read_message_id,
        db=db,
      )

      user_ids = await ChatService().get_chat_members(chat_id, db)      # Получаем ВСЕХ участников чата

    # Уведомляем других участников
    await websocket_manager.broadcast_to_users(
      user_ids=user_ids,                                                # Всем участникам
      data={
        "type": "chat_read",
        "chat_id": chat_id,
        "user_id": user_id,
        "last_read_message_id": last_read_message_id,
      },
      exclude_user_id=user_id,                                          # Кроме того, кто прочитал
    )