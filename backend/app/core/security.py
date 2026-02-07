from datetime import datetime, timedelta, timezone
from typing import Any 
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

 
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
 

def create_access_token(data: dict[str, Any], expires_minutes: int = 15) -> str:
	"""
	Создание access-токена
	"""

	to_encode = data.copy()

	minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
	expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)

	to_encode.update(
		{
		"exp": expire,
		"jti": str(uuid4()),
		"type": "access"
		}
	)

	return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any], expires_days: int = 7) -> tuple[str, str]:
	"""Создание refresh-токена"""

	to_encode = data.copy()

	days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
	expire = datetime.utcnow() + timedelta(days=days)
	
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