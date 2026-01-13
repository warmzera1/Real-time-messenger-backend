from app.services.message_service import MessageService
from app.database import get_db_session

import logging 

logger = logging.getLogger(__name__)


class DeliveryService:
  """Сервис для работы с доставкой сообщений"""

  @staticmethod
  async def mark_delivered(message_id: int, recipient_id: int) -> bool:
    async with get_db_session() as db:
      return await MessageService.mark_as_delivered(message_id, db)