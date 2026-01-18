import json 
import logging 
from typing import Optional, Callable, Awaitable

import aio_pika
from aio_pika import ExchangeType
from app.services.chat_read_service import ChatReadService 
from app.websocket.manager import websocket_manager
from app.database import get_db_session

logger = logging.getLogger(__name__)


class RabbitMQManager:
  """
  RabbitMQ менеджер
  1. Подключение
  2. Exchange 
  3. Публикация событий
  """

  def __init__(
    self,
    url: str = "amqp://guest:guest@localhost/",
    exchange_name: str = "chat.events",
  ):
    """Инициализация: сохраняет настройки, пока ничего не подключается"""

    self.url = url
    self.exchange_name = exchange_name 

    self.connection: Optional[aio_pika.RobustConnection] = None 
    self.channel: Optional[aio_pika.Channel] = None 
    self.exchange: Optional[aio_pika.Exchange] = None 

  
  async def connect(self):
    """Устанавливает соединение + создает канал + объявляет exchange"""

    logger.info("Подключение к RabbitMQ...")

    self.connection = await aio_pika.connect_robust(self.url)       # Надежное подключение, авто-reconnect
    self.channel = await self.connection.channel()              # Канал для операций

    self.exchange = await self.channel.declare_exchange(            # Создаем/получаем Exchange
      self.exchange_name,                                           
      ExchangeType.TOPIC,                                           # Тип topic - маршрутизация по шаблонам
      durable=True,                                                 # Сохраняется после перезагрузки
    )

    logger.info("RabbitMQ подключен")


  async def publish_event(
    self,
    routing_key: str,
    payload: dict,
  ):
    """
    Публикация события
    """

    # 1. Проверка, что exchange существует
    if not self.exchange:
      raise RuntimeError("RabbitMQ не подключен")
    
    # 2. Создает persistent сообщение (сохранится при перезагрузке)
    message = aio_pika.Message(
      body=json.dumps(payload).encode(),                              # Сериализует payload в JSON
      content_type="application/json",
      delivery_mode=aio_pika.DeliveryMode.PERSISTENT,                 # Сообщение сохраняется на диск
    )

    # 3. Отправляет по указанному routing_key
    await self.exchange.publish(
      message=message,
      routing_key=routing_key,
    )

    logger.debug(f"Публикация события: {routing_key}")


  async def consume(
    self,
    queue_name: str,
    routing_key: str,
    handler: Callable[[dict], Awaitable[None]],
    exchange_name: str = "chat.events",
  ):
    """Обработка сообщения из очереди"""
    
    # 1. Проверка подключения
    if not self.channel:
      raise RuntimeError("RabbitMQ не подключен")
    
    # 2. Объявляет/получает exchange
    exchange = await self.channel.declare_exchange(
      exchange_name,
      aio_pika.ExchangeType.TOPIC,
      durable=True,
    )

    # 3. Создает/получает очередь
    queue = await self.channel.declare_queue(
      queue_name,
      durable=True,
    )

    # 4. Привязывает очередь к exchange по ключу
    await queue.bind(exchange, routing_key)

    # 5. Внутренняя функция-обработчик
    async def on_message(message: aio_pika.IncomingMessage):
      # Подтверждает обработку
      async with message.process():
        # Парсит тело сообщения
        payload = json.loads(message.body.decode())
        # Вызывает передний обработчик
        await handler(payload)

    # 6. Запускает потребление
    await queue.consume(on_message)


# Глобальный инстанс
rabbit_manager = RabbitMQManager()