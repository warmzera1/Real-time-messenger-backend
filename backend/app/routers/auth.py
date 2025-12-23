from fastapi import APIRouter, Depends, HTTPException, status 
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.schemas.user import UserCreate 
from app.schemas.token import TokenResponse
from app.models.user import User 
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token


router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
  """Регистрация нового пользователя с выдачей access и refresh токенов"""

  # 1. Проверка существования
  existing_user = db.query(User).filter(
    or_(
      User.username == user_data.username,
      User.email == user_data.email,
    )
  ).first()

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
  db.commit()
  db.refresh(new_user)

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
async def login(username: str, password: str, db: Session = Depends(get_db)):
  """Логин пользователя"""

  # 1. Поиск пользователя
  user = db.query(User).filter(
    User.username == username
  ).first()

  # 2. Проверка существования пользователя и пароля
  if not user or verify_password(password, user.hashed_password):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Неверные учетные данные",
    )
  
  # 3. Payload и токены
  payload = {
    "sub": str(user.id)
  }
  access_token = create_access_token(payload)
  refresh_token = create_refresh_token(payload)

  # 4. Возвращаем ответ
  return TokenResponse(
    access_token=access_token,
    refresh_token=refresh_token,
    token_type="bearer",
  )


