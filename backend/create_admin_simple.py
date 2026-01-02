"""
Простой скрипт для создания администратора.
Использование: docker compose exec ai_service python create_admin_simple.py
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Добавляем путь для импортов
sys.path.insert(0, '/app')

from db.session import async_session_factory
from db.repository import get_user_by_username, create_user
from auth import get_password_hash

load_dotenv()

async def create_admin():
    """Создает администратора."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin1234")
    
    if not password:
        print("Ошибка: ADMIN_PASSWORD не установлен в .env")
        return
    
    hashed = get_password_hash(password)
    
    async with async_session_factory() as session:
        # Проверяем, существует ли уже пользователь
        existing_user = await get_user_by_username(session, username)
        if existing_user:
            print(f"Пользователь {username} уже существует")
            return
        
        # Создаем пользователя
        try:
            user = await create_user(
                session,
                username=username,
                email=os.getenv("ADMIN_EMAIL", f"{username}@example.com"),
                hashed_password=hashed,
                full_name="Administrator",
                role="admin",
            )
            print(f"Администратор {username} успешно создан!")
            print(f"ID: {user.id}")
        except Exception as e:
            print(f"Ошибка при создании администратора: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_admin())

