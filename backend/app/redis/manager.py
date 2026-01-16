import json
import logging 
import asyncio 
from typing import Optional, Set, Dict 
from datetime import datetime 

from redis.asyncio import Redis, ConnectionPool 
from redis.exceptions import RedisError, ConnectionError

logger = logging.getLogger(__name__)


class RedisManager:
  """
  Redis менеджер
  1. Управление подключениями с retry логикой
  2. Pub/Sub для сообщения между инстансами
  3. Хранение сессий и онлайн-статусами
  4. Graceful degradation при падении Redis
  """

  def __init__(
      self,
      host: str = "localhost",
      port: int = 6379,
      db: int = 0,
      max_connections: int = 20,
  ):
    # Connection pool вместо одного соединения
    self.pool = ConnectionPool(
      host=host,
      port=port,
      db=db,
      max_connections=max_connections,
      decode_responses=True,
      socket_keepalive=True,
      retry_on_timeout=True,
    )

    self.redis = Redis(connection_pool=self.pool)
    self._websocket_manager = None 

    # Pub/Sub состояние
    self._pubsub = None
    self._listening = False 
    self._listener_task: Optional[asyncio.Task] = None 

    # Кэш онлайн-статуса (оптимизация)
    self._online_cache: Dict[int, bool] = {}
    self._cache_ttl = 30        # Секунд
    self._last_cache_update: Dict[int, float] = {}

    # Метрики
    self.metrics = {
      "messages_published": 0,
      "messages_received": 0,
      "subscriptions": 0,
      "errors": 0,
      "reconnects": 0,
    }

    logger.info(f"RedisManager инициализирован: {host}:{port}")


  async def connect(self) -> bool:
    """Проверка подключений с retry"""

    try:
      await self.redis.ping()
      logger.info("Redis подключен")
      return True 
    
    except RedisError as e:
      logger.error(f"Не удалось подключиться к Redis: {e}")
      return False 
    

  # ============ СЕССИИ И ПОДПИСКИ ============

  async def add_user_session(self, user_id: int, session_id: str):
    """Добавление сессии пользователя"""

    try:
      key = f"user:sessions:{user_id}"
      await self.redis.sadd(key, session_id)
      await self.redis.expire(key, 3600)      # 1 час

      # Обновляем онлайн статус
      await self._set_user_online(user_id)
  
    except RedisError as e:
      logger.error(f"Ошибка добавления сессии: {e}")
      self.metrics["errors"] += 1


  async def remove_user_connection(self, user_id: int, session_id: str):
    """Удалении сессии пользователя"""

    try:
      key = f"user:sessions:{user_id}"
      await self.redis.srem(key, session_id)

      # Если сессии не осталось - пользователь оффлайн
      remaining = await self.redis.scard(key)
      if remaining == 0:
        await self._set_user_offline(user_id)

    except RedisError as e:
      logger.error(f"Ошибка удаления сессии: {e}")
      self.metrics["errors"] += 1

  
  async def is_user_online(self, user_id: int) -> bool:
    """Проверка онлайн-статуса с кэшированием"""

    # Проверяем кэш
    current_time = datetime.utcnow().timestamp()
    last_update = self._last_cache_update.get(user_id, 0)

    if user_id in self._online_cache and (current_time - last_update) < self._cache_ttl:
      return self._online_cache[user_id]
    
    # Получаем из Redis
    try:
      key = f"user:sessions:{user_id}"
      has_sessions = await self.redis.exists(key)

      # Обновляем кэш
      self._online_cache[user_id] = bool(has_sessions)
      self._last_cache_update[user_id] = current_time 

      return bool(has_sessions)
    
    except RedisError:
      # При ошибке Redis возвращаем значение из кэша или False
      return self._online_cache.get(user_id, False)
    

  async def _set_user_online(self, user_id: int):
    """Установить статус онлайн"""

    try:
      await self.redis.setex(f"user:online:{user_id}", 65, "1")     # TTL > heartbeat interval
      self._online_cache[user_id] = True 
      self._last_cache_update[user_id] = datetime.utcnow().timestamp()
    
    except RedisError as e:
      logger.error(f"Ошибка setting user {user_id} online: {e}")


  async def _set_user_offline(self, user_id: int):
    """Установить статус оффлайн"""

    try:
      await self.redis.delete(f"user:online:{user_id}")
      self._online_cache[user_id] = False 
      self._last_cache_update[user_id] = datetime.utcnow().timestamp()
    
    except RedisError:
      pass


  # ============ REFRESH-ТОКЕН ============

  async def add_refresh_token(self, jti: str, user_id: int, expires_seconds: int):
    """Сохраняем refresh-токен в Redis"""

    key = f"refresh:jti:{jti}"
    await self.redis.set(key, user_id, ex=expires_seconds)


  async def is_refresh_token_valid(self, jti: str) -> bool:
    """Проверяем, что refresh-токен еще валиден"""

    key = f"refresh:jti:{jti}"
    return await self.redis.exists(key)
  

  async def revoke_refresh_token(self, jti: str):
    """Удаляем refresh-токен из Redis"""
    key = f"refresh:jti:{jti}"
    await self.redis.delete(key)


  # ============ ПОДПИСКИ НА ЧАТЫ ============

  async def subscribe_to_chat(self, user_id: int, chat_id: int):
    """Подписать пользователя на чат"""

    try:
      key = f"chat:subscribers:{chat_id}"
      await self.redis.sadd(key, str(user_id))
      await self.redis.expire(key, 7200)    # 2 чата

      # Для быстрого поиска чатов пользователя
      user_chats_key = f"user:chats:{user_id}"
      await self.redis.sadd(user_chats_key, str(chat_id))
      await self.redis.expire(user_chats_key, 7200)  

      self.metrics["subscriptions"] += 1
      logger.debug(f"Пользователь {user_id} подписан на чат {chat_id}")

    except RedisError as e:
      logger.error(f"Ошибка подписки: {e}")
      self.metrics["errors"] += 1


  async def unsubscribe_from_chat(self, user_id: int, chat_id: int):
    """Отписать пользователя от чата"""

    try:
      key = f"chat:subscribers:{chat_id}"
      await self.redis.srem(key, str(user_id))

      # Обновляем список чатов пользователя
      user_chats_key = f"user:chats:{user_id}"
      await self.redis.srem(user_chats_key, str(chat_id))

      logger.debug(f"Пользователь {user_id} отписан от чата {chat_id}")

    except RedisError as e:
      logger.error(f"Ошибка отписки: {e}")
      self.metrics["errors"] += 1


  async def get_chat_subscribers(self, chat_id: int) -> Set[str]:
    """Получить подписчиков чата"""

    try:
      key = f"chat:subscribers:{chat_id}"
      subscribers = await self.redis.smembers(key)
      return subscribers 

    except RedisError:
      return set()
    

  # ============ PUB/SUB ДЛЯ СООБЩЕНИЙ ============  

  async def publish_chat_message(
    self,
    chat_id: int,
    message_data: dict,
    retries: int = 2,
  ) -> bool:
    """
    Публикация сообщения в чате с retry логикой
    Возвращает True при успехе
    """

    for attempt in range(retries + 1):
      try:
        channel = f"chat:messages:{chat_id}"
        await self.redis.publish(channel, json.dumps(message_data))
        return True 
      
      except RedisError as e:
        if attempt == retries:
          logger.error(f"Не удалось опубликовать сообщение после {retries} попыток: {e}")
          self.metrics["errors"] += 1
        else:
          logger.warning(f"Попытка {attempt + 1} публикация не удалась: {e}")
          await asyncio.sleep(0.5 * (attempt + 1))

    return False 
  

  # ============ СЛУШАТЕЛЬ PUB/SUB ============

  async def start_listening(self):
    """Запуск слушателя Redis Pub/Sub"""

    if self._listening:
      return 

    try:
      self._listening = True 
      self._pubsub = self.redis.pubsub()

      # Подписываемся на все каналы сообщений
      await self._pubsub.psubscribe("chat:messages:*")

      # Запускаем слушателя в фоне
      self._listening_task = asyncio.create_task(self._listen_loop())

      logger.info(f"Redis Pub/Sub слушатель запущен")

    except Exception as e:
      logger.error(f"Ошибка запуска слушателя: {e}")
      self._listening = False 
      self.metrics["errors"] += 1

  
  async def _listen_loop(self):
    """Основной цикл слушателя"""

    while self._listening:
      try:
        async for message in self._pubsub.listen():
          if message["type"] == "pmessage":
            await self._handle_pubsub_message(message)

      except ConnectionError:
        logger.warning("Потеряно соединение с Redis, переподключение...")
        self.metrics["reconnects"] += 1
        await asyncio.sleep(2)
        await self._reconnect()
      except Exception as e:
        logger.error(f"Ошибка в цикле слушателя: {e}")
        self.metrics["errors"] += 1
        await asyncio.sleep(1)


  async def _handle_pubsub_message(self, message: dict):
    """Обработка сообщения из Pub/Sub"""

    try:
      channel = message["channel"]    # Например "chat:messages:123"

      if not channel.startswith("chat:messages:"):
        return # Не наш канал
      
      # Извлекаем chat_id из канала
      chat_id = int(channel.split(":")[2])
      data = json.loads(message["data"])
      message_id = data["id"]

      # Получаем подписчиков чата
      subscribers = await self.get_chat_subscribers(chat_id)

      if not subscribers:
        logger.debug(f"Нет подписчиков для чата {chat_id}")
        return 
      
      # Отправляем сообщение через WebSocketManager
      total_sent = 0
      if self._websocket_manager:
        for user_id_str in subscribers:
          user_id = int(user_id_str)

          # Проверяем онлайн статус
          if await self.is_user_online(user_id):
            sent_count = await self._websocket_manager.send_to_user(user_id, {
              "type": "chat_message",
              "data": data,
            })
            total_sent += sent_count 
          
      # Если хотя бы один пользователь получил сообщение, обновляем delivered_at
      if total_sent > 0:
        from app.services.message_service import MessageService
        from app.database import get_db_session

        async with get_db_session() as db:
          await MessageService().mark_as_delivered(
            message_id=message_id,
            db=db,
          )

      self.metrics["messages_received"] += 1

    except Exception as e:
      logger.error(f"Ошибка обработки Pub/Sub сообщения: {e}")
      self.metrics["errors"] += 1


  async def _reconnect(self):
    """Переподключение к Redis"""

    try:
      if self._pubsub:
        await self._pubsub.close()

      await self.redis.close()

      # Создаем новое соединение
      self.redis = Redis(connection_pool=self.pool)

      # Перезапускаем слушателя
      if self._listening:
        await self.start_listening()
    
    except Exception as e:
      logger.error(f"Ошибка переподключения: {e}")


  # ============ СВЯЗЬ С WEBSOCKET MANAGER ============

  def set_websocket_manager(self, manager):
    """Ссылка на WebSocketManager"""

    self._websocket_manager = manager 

  
  # ============ МЕТРИКИ И СТАТУС ============

  async def get_stats(self) -> dict:
    """Получить статистику Redis"""

    try:
      info = await self.redis.info()
      return {
        **self.metrics,
        "redis_connected": True,
        "redis_used_memory": info.get("used_memory_human", "N/A"),
        "redis_connecntions": info.get("connected_clients", 0),
        "timestamp": datetime.now().isoformat(),
      }
    
    except RedisError:
      return {
        **self.metrics,
        "redis_connected": False,
        "timestamp": datetime.now().isoformat(),
      }
    

  # ============ ЗАКРЫТИЕ ============

  async def close(self):
    """Закрытие соединений"""

    try:
      self._listening = False 

      if self._listener_task:
        self._listener_task.cancel()
        try:
          await self._listener_task
        except asyncio.CancelledError:
          pass
      
      if self._pubsub:
        await self._pubsub.close()

      await self.redis.close()
      await self.pool.disconnect()

      logger.info(f"RedisManager закрыт")

    except Exception as e:
      logger.error(f"Ошибка закрытия RedisManager: {e}")


# Глобальный инстанс
redis_manager = RedisManager() 


