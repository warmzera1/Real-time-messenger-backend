from passlib.context import CryptContext
from datetime import datetime, timedelta 
from jose import JWTError, jwt 
from app.core.config import settings


# Контекст для работы с хешами 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
  """
  Проверка пароля пользователя при авторизации
  Сравниваем введный пароль с хешированным в БД
  """

  return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
  """
  Хеширование пароля при регистрации пользователя
  Сохраняет в БД только пароль с хеш
  """

  return pwd_context.hash(password)
 

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
  """
  Создание access-токена
  """

  # 1. Копируем данные, которые нужно закодировать в JWT-токен
  to_encode = data.copy()

  # 2. Вычисляем время жизни acccess-токена
  if expires_delta:
    expire = datetime.utcnow() + expires_delta
  else:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

  # 3. Добавляем время истечения payload
  to_encode.update(
    {
      "exp": expire
    }
  )

  # 3. Возвращаем закодированный JSON Web Token
  encoded_jwt = jwt.encode(
          to_encode, 
          settings.SECRET_KEY, 
          algorithm=settings.ALGORITHM
  )

  return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
  """Создание refresh-токена"""

  # 1. Копируем данные, которые нужно закодировать в JWT-токен
  to_encode = data.copy()

  # 2. Вычисляем время жизни refresh-токена
  if expires_delta:
    expire = timedelta.utcnow() + expires_delta
  else:
    expire = timedelta.utcnow() + timedelta(settings.REFRESH_TOKEN_EXPIRE_DAYS)

  # 3. Добавляем exp в payload 
  to_encode.update(
    {
      "exp": expire
    }
  )

  # 4. Возвращаем закодированные JSON Web Token 
  encoded_jwt = jwt.encode(
      to_encode,
      settings.SECRET_KEY,
      algorithm=settings.ALGORITHM,
  )

  return encoded_jwt