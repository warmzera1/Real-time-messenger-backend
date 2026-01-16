from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from jose import jwt, JWTError

from app.database import get_db
from app.schemas.user import UserCreate, LoginForm
from app.schemas.token import TokenResponse, RefreshTokenRequest
from app.models.user import User 
from app.redis.manager import redis_manager
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
  """Регистрация нового пользователя с выдачей access и refresh токенов"""

  # 1. Проверка существования
  stmt = select(User).where(
    or_(
      User.username == user_data.username,
      User.email == user_data.email,
    )
  )
  result = await db.execute(stmt)
  existing_user = result.scalar_one_or_none()

  # 2. Если существует - ошибка
  if existing_user:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Пользователь с таким Email или Username уже зарегистрирован",
    )
  
  # 3. Хешируем пароль
  hashed = get_password_hash(user_data.password)

  # 4. Создаем объект User и сохраняем в БД
  new_user = User(
    username=user_data.username,
    email=user_data.email,
    hashed_password=hashed,
  )

  db.add(new_user)
  await db.commit()
  await db.refresh(new_user)

  # 5. Payload и токены
  payload = {
    "sub": str(new_user.id),
  }
  access_token = create_access_token(payload)
  refresh_token = create_refresh_token(payload)

  # 6. Возвращаем ответ
  return TokenResponse(
    access_token=access_token,
    refresh_token=refresh_token,
    token_type="bearer",
  )


@router.post("/login", response_model=TokenResponse)
async def login(form: LoginForm, db: AsyncSession = Depends(get_db)):
  """Логин пользователя"""

  identifier = form.get_identifier()
  if not identifier:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Укажите username или email",
    )

  # 1. Поиск пользователя
  stmt = select(User).where(
    (User.username == identifier) | (User.email == identifier)
  )
  result = await db.execute(stmt)
  user = result.scalar_one_or_none()

  # 2. Проверка существования пользователя и пароля
  if not user or not verify_password(form.password, user.hashed_password):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Неверные учетные данные",
    )
  
  # 3. Payload и токены
  payload = {
    "sub": str(user.id)
  }
  access_token = create_access_token(payload)
  refresh_token, jti = create_refresh_token(payload)

  await redis_manager.add_refresh_token(jti, user.id, expires_seconds=7*24*3600)

  # 4. Возвращаем ответ
  return TokenResponse(
    access_token=access_token,
    refresh_token=refresh_token,
    token_type="bearer",
  )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
  """Обновление access-токена по refresh-токену"""

  try: 
    # 1. Декодируем refresh токен
    payload = jwt.decode(
      data.refresh_token,
      settings.SECRET_KEY,
      algorithms=[settings.ALGORITHM]
    )
    if payload.get("type") != "refresh":
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Невалидный refresh токен",
      )
    jti = payload.get("jti")
    user_id: str = payload.get("sub")

    if not jti or not user_id:
      raise HTTPException(
        status_code=status.HTTP_410_UNAUTHORIZED,
        detail="Невалидный refresh токен",
      )
    
  # 3. Если токен поврежден - ошибка
  except JWTError:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Невалидный refresh токен",
    )
  
  if not await redis_manager.is_refresh_token_valid(jti):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Refresh токен истек или отозван"
    )
  
  await redis_manager.revoke_refresh_token(jti)
  
  # 4. Поиск пользователя в БД
  result = await db.execute(
    select(User).where(User.id == int(user_id))
  )
  user = result.scalar_one_or_none()

  if not user or not user.is_active:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Пользователь не существует или неактивен"
    )
  
  # 4. Новые токены (rotating refresh)
  new_access = create_access_token({"sub": user_id})
  new_refresh, new_jti = create_refresh_token({"sub": user_id})

  await redis_manager.add_refresh_token(
      new_jti, 
      int(user_id), 
      expires_seconds=7*24*3600
  )

  # 5. Возвращаем ответ
  return TokenResponse(
    access_token=new_access,
    refresh_token=new_refresh,
    token_type="bearer",
  )
  


