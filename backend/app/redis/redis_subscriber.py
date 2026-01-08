import asyncio
import json
import logging 
from typing import Dict, Set 
from redis.asyncio.client import PubSub


logger = logging.getLogger(__name__)


class DynamicRedisSubscriber:
  """
  Динамический подписчик на Redis каналы
  """

  def __init__(self, redis_manager, websocket_manager):
    self.redis = redis_manager.redis 
    self.websocket = websocket_manager
    self.pubsub = None
    self.running = False 

    # Динамические подписки: channel -> set(user_ids)
    self.channel_subscriptions: Dict[str, Set[int]] = {}

    # Обратные подписки: user_id -> set(channels)
    self.user_subscriptions: Dict[int, Set[str]] = {}

    # Lock для безопасного доступа к словарям
    self._lock = asyncio.Lock()     # Создание асинхронной блокировки


  async def start(self):
    """Запуск подписчика"""

    if self.running:
      return 
    
    self.running = True 
    self.pubsub = self.redis.pubsub()

    # Запускаем обработчик сообщений
    asyncio.create_task(self._message_processor())

    logger.info(f"Dynamic Redis Subscriber запущен")


  async def stop(self):
    """Остановка подписчика"""

    self.running = False 

    if self.pubsub:
      await self.pubsub.close()
    
    logger.info("Dynamic Redis Subscription остановлен")


  async def subscribe_user(self, user_id: int):
    """
    Подписка пользователя на его событие (чаты, уведомления, обновления)
    Возвращает список каналов, на которые подписались
    """

    async with self._lock:    # Защищает от одновременного вызова несколькими корутинами
      try:
        # Получаем чаты пользователя
        from app.services.chat_services import ChatService
        chat_service = ChatService()
        chats = await chat_service.get_user_chats(user_id)
        chat_ids = [chat.id for chat in chats]    # Список ID чатов 

        logger.info(f"Подписка пользователя {user_id} на {len(chat_ids)} чатов")

        subscribed_channels = []    # Список успешно подписанных каналов

        # 1. Подписка на событие каждого чата
        for chat_id in chat_ids:
          # Канал новых сообщений в чате
          channel = f"chat:{chat_id}:message"
          if await self._add_user_to_channel(user_id, channel):
            subscribed_channels.append(channel)

          # Канал обновлений чата (например, участники, название)
          update_channel = f"chat:{chat_id}:updates"
          if await self._add_user_to_channel(user_id, update_channel):
            subscribed_channels.append(update_channel)

        # 2. Личный канал уведомлений пользователя
        notification_channel = f"user:{user_id}:notifications"
        if await self._add_user_to_channel(user_id, notification_channel):
          subscribed_channels(notification_channel)

        # 3. Канал обновлений профиля пользователя
        profile_channel = f"user:{user_id}:updates"
        if await self._add_user_to_channel(user_id, profile_channel):
          subscribed_channels(profile_channel)

        logger.info(f"Пользователь {user_id} подписан на {len(subscribed_channels)} каналов")
        return subscribed_channels
      
      except Exception as e:
        logger.error(f"Ошибка подписки пользователя {user_id}: {e}")
        return []


  async def unsubscribe_user(self, user_id: int):
    """
    Отписывает пользователя от всех его каналов (при отключении WebSocket)
    """

    async with self._lock:    # Защищает словари от единого доступа
      try:
        # Если у пользователя нет подписок - ничего не делаем 
        if user_id not in self.user_subscriptions:
          logger.debug(f"Пользователь {user_id} не имеет подписок")
          return 
        
        # Удаляем набор каналов пользователя
        user_channels = self.user_subscriptions.pop(user_id, set())

        # Проходим по каждому каналу
        for channel in user_channels:
          if channel in self.user_subscriptions:
            # Удаляем пользователя из сети подписчиков канала
            self.channel_subscriptions[channel].discard(user_id)

            # Если в канале никого не осталось
            if not self.channel_subscriptions[channel]:
              # Отписываемся от канала в Redis
              await self.pubsub.unsubscribe(channel)
              # Удаляем пустой канал из локального словаря
              del self.channel_subscriptions[channel]

        logger.info(f"Пользователь {user_id} отписан от {len(user_channels)} каналов")

      except Exception as e:
        logger.error(f"Ошибка отписки пользователя {user_id}: {e}")


  async def _add_user_to_channel(self, user_id: int, channel: str) -> bool:
    """
    Добавляет пользователя в локальные подписки и, если нужно, подписываем на канал в Redis
    Возвращает True, если была выполнена подписка в Redis (первый подписчик)
    """

    try:
      # Ининциализация структур данных, если они еще не существуют
      if channel not in self.channel_subscriptions:
        self.channel_subscriptions[channel] = set()   # Сет подписчиков канала

      if user_id not in self.channel_subscriptions:
        self.user_subscriptions[user_id] = set()    # Сет каналов пользователя

      # Проверяем, был ли канал пустым до добавления 
      subscribe_in_redis = len(self.channel_subscriptions[channel]) == 0

      # Добавляем связи в память
      self.channel_subscriptions[channel].add(user_id)  # user -> channel
      self.channel_subscriptions[user_id].add(channel)  # channel -> user

      # Если это первый подписичк - подписываемся на канал в Redis
      if subscribe_in_redis:
        await self.pubsub.subscribe(channel)
        logger.debug(f"Подписались в Redis на канал: {channel}")

      return subscribe_in_redis
    
    except Exception as e:
      logger.error(f"Ошибка добавления в канал {channel}: {e}")
      return False 
    

  async def remove_user_from_chat(self, user_id: int, chat_id: int):
    """
    Удаляет пользователя из подписок на события чата (при выходе из чата)
    """

    async with self._lock:    # Защита от одновременных изменений
      try:
        # Два канала чата: сообщения и обновления
        channels = [
          f"chat:{chat_id}:messages",
          f"chat:{chat_id}:updates"
        ]

        for channel in channels:
          if channel in self.channel_subscriptions:
            # Удаляем пользователя из подписчиков канала
            self.channel_subscriptions[channel].discard(user_id)

            # Удаляем канал из списка пользователя
            if user_id in self.user_subscriptions:
              self.user_subscriptions[user_id].discard(channel)

            # Если в канале никого не осталось
            if not self.channel_subscriptions[channel]:
              # Отписываемся от канала в Redis
              await self.pubsub.unsubscribe(channel)
              # Удаляем пустой канал из памяти
              del self.channel_subscriptions[channel]

        logger.info(f"Пользователь {user_id} удален из подписок чата {chat_id}")

      except Exception as e:
        logger.error(f"Ошибка удаления пользователя {user_id} из чата {chat_id}: {e}")


# Глобальный экземпляр
redis_subscriber = None 


def get_redis_subscriber():
  """
  Ленивая инициализация подписчика
  """

  global redis_subscriber
  if redis_subscriber is None:
    from app.redis.manager import redis_manager
    from app.websocket.manager import websocket_manager
    redis_subscriber = DynamicRedisSubscriber(redis_manager, websocket_manager)
  return redis_subscriber