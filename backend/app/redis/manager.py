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

redis_manager = RedisManager()