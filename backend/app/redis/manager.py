from redis.asyncio import Redis 
from typing import Optional, Set, Dict 
import json 
import logging 
from datetime import datetime 


logger = logging.getLogger(__name__)


class RedisManager:
  """
  Менеджер для асинхронной работы с Redis
  """

  def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
    """
    Инициализация подключения к Redis
    Подключаемся к базе данных в памяти
    """

    self.redis = Redis(
      host=host,
      port=port,
      db=db,
      decode_responses=True,      # Автоматически декодируем bytes -> str
      socket_keepalive=True,     #  Поддержание соединения
    )
    logger.info(f"RedisManager инициализирован: {host}:{port}")


  async def connect(self):
    """
    Проверка подключения к Redis
    """

    try:
      # Отправляем PING и ждем PONG
      pong = await self.redis.ping()
      if pong:
        logger.info(f"[connect] Redis подключен")
        return True
      
    except Exception as e:
      logger.error(f"[connect] Ошибка при подключении к Redis: {e}")
      return False
    

  # ============ ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ============   
  async def cache_user_profile(self, user_id: int, user_data: dict, ttl: int = 60):
    """
    Кэшируем профиль пользователя
    ttl = Time To Live (время жизни кэша в секундах)
    """
    
    cache_key = f"user:profile:{user_id}"
    try:
      await self.redis.setex(
        cache_key,
        ttl,
        json.dumps(user_data)
      )
      logger.debug(f"[cache_user_profile] Профиль user: {user_id} закэширован на {ttl} секунд")
    
    except Exception as e:
      logger.error(f"[cache_user_profile] Ошибка кэширования профиля: {e}")


  async def get_cached_user_profile(self, user_id: int) -> dict | None:
    """Получить профиль пользователя из кэша"""

    cache_key = f"user:profile:{user_id}"
    try:
      cached = await self.redis.get(cache_key)
      if cached:
        return json.loads(cached)
    
    except Exception as e:
      logger.error(f"[get_cached_user_profile] Ошибка получения кэша профиля: {e}")
    return None 
  

  # ============ СОЕДИНЕНИЯ WEB SOCKET ============
  async def add_websocket_connection(self, chat_id: int, websocket_id: str, user_id: int):
    """
    Регистрирует WebSocket соединение
    Используется в ConnectionManager
    """

    try:
      # 1. Chat -> WebSocket
      await self.redis.sadd(f"chat:{chat_id}:connections", websocket_id)

      # 2. WebSocket -> User
      await self.redis.setex(f"ws:{websocket_id}", 300, user_id)

      logger.info(f"[add_connection] Добавлено WebSocket соединение: {websocket_id[:8]} для пользователя user: {user_id}")

    except Exception as e:
      logger.error(f"[add_connection] Ошибка добавления WebSocket соединения: {e}")

  
  async def remove_websocket_connection(self, chat_id: int, websocket_id: str):
    """
    Удаляет WebSocket соединение
    """

    try:
      # 1. Удаляем WebSocket -> User
      await self.redis.delete(f"ws:{websocket_id}")

      # 2. Удаляем из чата
      await self.redis.srem(f"chat:{chat_id}:connections", websocket_id)

      logger.info(f"[remove_websocket_connections] WebSocket {websocket_id[:8]} удален")

    except Exception as e:
      logger.error(f"[remove_websocket_connections] Ошибка: {e}")


   # ============ ХРАНЕНИЕ АКТИВНЫХ СОЕДИНЕНИЙ ПОЛЬЗОВАТЕЛЯ ============
  async def register_user_connection(self, user_id: int, ws_id: str, server_id: int):
    """
    Регистрация соединения пользователя
    """

    # Ключ: user_connections:{user_id}
    key = f"user_connections:{user_id}"
    await self.redis.hset(key, ws_id, server_id)
    await self.redis.expire(key, 3600)  # TTL 1 чаc

  
  async def unregister_user_connection(self, user_id: int, ws_id: str):
    """
    Удаление соединения пользователя
    """

    key = f"user_connections:{user_id}"
    await self.redis.hdel(key, ws_id)


  async def get_user_connections(self, user_id: int) -> Dict[str, str]:
    """
    Получение всех соединений пользователя
    """

    key = f"user_connections:{user_id}"
    await self.redis.hgetall(key)


   # ============ Pub/Sub ============
  async def subscribe_to_chat_messages(self, user_id: int, chat_id: int):
    """
    Подписка пользователя на сообщения чата
    """

    key = f"user_subscriptions:messages:{user_id}"
    await self.redis.sadd(key, str(chat_id))


  async def publish_chat_message(self, chat_id: int, message_data: dict):
    """
    Публикация нового сообщения
    """

    channel = f"chat:{chat_id}:messages"
    await self.redis.publish(channel, json.dumps(message_data))

  
  async def publish_user_updates(self, user_id: int, update_data: dict):
    """
    Публикация обновления пользователя
    """

    channel = f"user:{user_id}:updates"
    await self.redis.publish(channel, json.dumps(update_data))



redis_manager = RedisManager()