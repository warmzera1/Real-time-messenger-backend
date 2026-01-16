from passlib.context import CryptContext
from datetime import datetime, timedelta 
from jose import JWTError, jwt
from uuid import uuid4
from app.core.config import settings


# Контекст для работы с хешами 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM 
SECRET_KEY = settings.SECRET_KEY


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
 

def create_access_token(data: dict, expires_minutes: int = 15) -> str:
  """
  Создание access-токена
  """

  # 1. Копируем данные, которые нужно закодировать в JWT-токен
  to_encode = data.copy()

  # 2. Время жизни токена access-токена
  expire = datetime.utcnow() + timedelta(minutes=expires_minutes)

  # 3. Добавляем в payload
  to_encode.update({
    "exp": expire,
    "jti": str(uuid4()),
    "type": "access",
  })

  return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_days: int = 7) -> tuple[str, str]:
  """Создание refresh-токена"""

  # 1. Копируем данные, которые нужно закодировать в JWT-токен
  to_encode = data.copy()

  # 2. Вычисляем время жизни refresh-токена
  expire = datetime.utcnow() + timedelta(days=expires_days)

  # 3. Добавляем в payload 
  jti = str(uuid4())
  to_encode.update(
    {
      "exp": expire,
      "jti": jti,
      "type": "refresh",
    }
  )

  token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
  return token, jti