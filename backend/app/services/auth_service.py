from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from jose import jwt, JWTError

from app.schemas.user import UserCreate, LoginForm
from app.schemas.token import TokenResponse, RefreshTokenRequest
from app.models.user import User 
from app.redis.manager import redis_manager
from app.core.security import (
  get_password_hash, 
  verify_password, 
  create_access_token, 
  create_refresh_token
)
from app.core.config import settings


class AuthService:

    @staticmethod 
    async def register(user_data: UserCreate, db: AsyncSession) -> TokenResponse:
        """Регистрация нового пользователя"""

        stmt = select(User).where(
            or_(
                User.username == user_data.username,
                User.email == user_data.email,
            )
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("USER_EXISTS")

        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        payload = {"sub": str(user.id)}
        access = create_access_token(payload)
        refresh, jti = create_refresh_token(payload)

        await redis_manager.add_refresh_token(
            jti=jti,
            user_id=user.id,
            expires_seconds=7 * 24 * 3600,
        )

        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
        )

    @staticmethod 
    async def login(form: LoginForm, db: AsyncSession) -> TokenResponse:
        """Авторизация пользователя"""

        identifier = form.get_identifier()
        if not identifier:
            raise ValueError("NO_IDENTIFIER")

        stmt = select(User).where(
            (User.username == identifier) | (User.email == identifier)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(form.password, user.hashed_password):
            raise ValueError("INVALID_CREDENTIALS")
    
        payload = {"sub": str(user.id)}
        access = create_access_token(payload)
        refresh, jti = create_refresh_token(payload)

        await redis_manager.add_refresh_token(jti, user.id, expires_seconds=7*24*3600) 

        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
        )

    @staticmethod 
    async def refresh_token(data: RefreshTokenRequest, db: AsyncSession) -> TokenResponse:
        """Обновление access-токена по refresh-токену"""

        try: 
            payload = jwt.decode(
                data.refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
        except JWTError:
            raise ValueError("INVALID_REFRESH")
    
        if payload.get("type") != "refresh":
            raise ValueError("INVALID_REFRESH")
    
        jti = payload.get("jti")
        user_id: str = payload.get("sub")

        if not jti or not user_id:
            raise ValueError("INVALID_REFRESH")
    
        if not await redis_manager.is_refresh_token_valid(jti):
            raise ValueError("REFRESH_REVOKED")
    
        await redis_manager.revoke_refresh_token(jti)
    
        result = await db.execute(
            select(User).where(User.id == int(user_id))
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise ValueError("USER_INACTIVE")
    
        new_access = create_access_token({"sub": user_id})
        new_refresh, new_jti = create_refresh_token({"sub": user_id})

        await redis_manager.add_refresh_token(
            new_jti, 
            int(user_id), 
            expires_seconds=7*24*3600
        )

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
        )
  
    @staticmethod 
    async def logout(refresh_token: str, current_user: int) -> None:
        """Выход пользователя из аккаунта"""

        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except JWTError:
            raise ValueError("INVALID_TOKEN")

        if payload.get("type") != "refresh":
            raise ValueError("INVALID_TOKEN")
    
        if str(current_user) != payload.get("sub"):
            raise ValueError("FORBIDDEN")
    
        jti = payload.get("jti")
        if not jti:
            raise ValueError("INVALID_TOKEN")
  
        if not await redis_manager.is_refresh_token_valid(jti):
            raise ValueError("ALREADY_REVOKED")
    
        await redis_manager.revoke_refresh_token(jti)
 
