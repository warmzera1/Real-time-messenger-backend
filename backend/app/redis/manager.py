import json 
import logging 
from datetime import datetime 

from redis.asyncio import Redis 

logger = logging.getLogger(__name__)


class RedisManager:
  """Redis-менеджер для чата"""

  def __init__(self, url: str = "redis://localhost:6379/0"):
    self.redis = Redis.from_url(url, decode_responses=True)


  # ===== ОНЛАЙН СТАТУС =====

  async def mark_user_online(self, user_id: int):
    """Отмечаем пользователя онлайн (TTL 90 сек)"""

    key = f"online:{user_id}"
    await self.redis.setex(key, 90, "1")

  
  async def mark_user_offline(self, user_id: int):
    """Удаляем отметку оффлайн"""

    key = f"online:{user_id}"
    await self.redis.delete(key)

  
  async def is_user_online(self, user_id: int) -> bool:
    """Проверка онлайн-статуса"""

    key = f"online:{user_id}"
    return bool(await self.redis.exists(key))
  

  # ===== ДОБАВИТЬ / УДАЛИТЬ ИЗ ЧАТА =====

  async def add_user_to_chat(self, user_id: int, chat_id: int):
    """Добавляем пользователя в набор участников чата"""

    key = f"chat_members:{chat_id}"
    await self.redis.sadd(key, str(user_id))

  
  async def remove_user_from_chat(self, user_id: int, chat_id: int):
    """Удаляем пользователя из чата"""

    key = f"chat_members:{chat_id}"
    await self.redis.delete(key, str(user_id))
  

  # ===== ПУБЛИКАЦИЯ СООБЩЕНИЙ В ЧАТЕ =====

  async def publish_to_chat(self, chat_id: int, message: dict):
    """Публикуем сообщение в канал чата"""

    channel = f"chat:{chat_id}"
    await self.redis.publish(channel, json.dumps(message))


  # ===== ОФФЛАЙН - СООБЩЕНИЯ =====

  async def store_offline_message(self, user_id: int, message: dict):
    """Добавляем сообщение в очередь оффлайн"""

    key = f"offline:{user_id}"
    await self.redis.rpush(key, json.dumps(message))
    # Ограничиваем размер очереди
    await self.redis.ltrim(key, -300, -1)                         # Храним максимум 300 последних

  
  async def get_and_remove_offline_messages(self, user_id: int) -> list[dict]:
    """Получаем и сразу удаляем все отложенные сообщения"""

    key = f"offline:{user_id}"
    messages = await self.redis.lrange(key, 0, -1)
    if messages:
      await self.redis.delete(key)
    return [json.loads(m) for m in messages]
  

  # ===== PUB / SUB СЛУШАТЕЛЬ =====

  async def subscribe_to_chats(self, callback):
    """
    Запускаем Pub/Sub слушатель
    callback вызывается для каждого полученного сообщения
    """

    pubsub = self.redis.pubsub()
    await pubsub.psubscribe("chat:*")

    async for message in pubsub.listen():
      if message["type"] != "pmessage":
        continue 

      try:
        channel = message["channel"]        # chat:123
        chat_id = int(channel.split(":", 1)[1])
        data = json.loads(message["data"])

        await callback(chat_id, data)

      except Exception as e:
        logger.error(f"Pub/Sub ошибка: {e}", exc_info=True)


  # ===== RATE LIMITING =====
  async def rate_limiting_check(self, user_id: int, max_requests: int = 5, window_sec: int = 10) -> bool:
    key = f"ratelimit:msg:{user_id}"
    now = int(datetime.utcnow().timestamp())

    await self.redis.zremrangebyscore(key, "-inf", now - window_sec)
    count = await self.redis.zcard(key)
    if count >= max_requests:
      return False 
    
    await self.redis.zadd(key, {str(now): now})
    await self.redis.expire(key, window_sec + 10)
    
    return True 


  # ===== REFRESH - ТОКЕН =====

  async def add_refresh_token(self, jti: str, user_id: int, expires_seconds: int):
    """Сохраняем refresh-токен"""

    key = f"refresh_jti:{jti}"
    await self.redis.set(key, user_id, ex=expires_seconds)


  async def is_refresh_token_valid(self, jti: str) -> bool:
    """Проверяем, что refresh-токен еще валиден"""

    key = f"refresh_jti:{jti}"
    return await self.redis.exists(key)
  

  async def revoke_refresh_token(self, jti: str):
    """Удаляем refresh-токен из Redis"""

    key = f"refresh_jti:{jti}"
    await self.redis.delete(key)


  # ===== ЗАКРЫТИЕ =====

  async def close(self):
    await self.redis.close()


redis_manager = RedisManager()
