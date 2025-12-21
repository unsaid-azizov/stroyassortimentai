"""
Модуль аутентификации для CRM панели.
Использует JWT токены и проверку пароля через БД.
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv

from db.session import async_session_factory
from db.repository import get_user_by_username, update_user_last_login

load_dotenv()

# Конфигурация
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

# HTTP Bearer для извлечения токена
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль."""
    if not hashed_password:
        return False
    try:
        # Используем прямой вызов bcrypt
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        # Логируем ошибку, но не падаем
        import logging
        logging.error(f"Error verifying password: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Хеширует пароль."""
    # Используем прямой вызов bcrypt
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создает JWT токен."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Проверяет JWT токен и возвращает данные пользователя."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"username": username}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Проверяет учетные данные пользователя через БД.
    Возвращает данные пользователя или None если неверные.
    """
    async with async_session_factory() as session:
        user = await get_user_by_username(session, username)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        # Обновляем время последнего входа
        await update_user_last_login(session, user.id)
        
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name
        }

