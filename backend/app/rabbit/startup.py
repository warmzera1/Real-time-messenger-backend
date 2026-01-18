from app.rabbit.manager import rabbit_manager
from app.rabbit.consumers.message_created import MessageCreatedConsumer
from app.rabbit.consumers.chat_read import ChatReadConsumer


async def start_consumers():
  """Запускает потребителя событий message.created для WebSocket уведомлений"""
 

  await rabbit_manager.consume(         # Запускает потребителя сообщений
    queue_name="message.created.ws",    # Имя очереди
    routing_key="message.created",      # Ключ маршрутизации
    handler=MessageCreatedConsumer().handle,            # Функция-обработчик каждого сообщения
  )


  await rabbit_manager.consume(
    queue_name="chat.read.db",        
    routing_key="chat.read",
    handler=ChatReadConsumer().handle,    
  )