from app.rabbit.manager import rabbit_manager
from app.rabbit.consumers.message_created import MessageCreatedConsumer


async def start_consumers():
  """Запускает потребителя событий message.created для WebSocket уведомлений"""

  consumer = MessageCreatedConsumer()   

  await rabbit_manager.consume(         # Запускает потребителя сообщений
    queue_name="message.created.ws",    # Имя очереди
    routing_key="message.created",      # Ключ маршрутизации
    handler=consumer.handle,            # Функция-обработчик каждого сообщения
  )