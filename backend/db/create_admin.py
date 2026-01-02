"""
Скрипт для создания первого администратора в БД.
Использование: python -m db.create_admin
"""
import asyncio
import os
from dotenv import load_dotenv
from db.session import async_session_factory
from db.repository import get_user_by_username, create_user
from auth import get_password_hash

load_dotenv()

async def create_admin_user():
    """Создает администратора из переменных окружения."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "")
    
    if not password:
        print("Ошибка: ADMIN_PASSWORD не установлен в .env")
        return
    
    async with async_session_factory() as session:
        # Проверяем, существует ли уже пользователь
        existing_user = await get_user_by_username(session, username)
        if existing_user:
            # Ensure role=admin for the configured admin user (backward compat)
            try:
                if getattr(existing_user, "role", "manager") != "admin":
                    existing_user.role = "admin"
                    await session.commit()
                    await session.refresh(existing_user)
                    print(f"Пользователь {username} уже существует — роль обновлена на admin")
                else:
                    print(f"Пользователь {username} уже существует (admin)")
            except Exception as e:
                print(f"Пользователь {username} уже существует, но не удалось обновить роль: {e}")
            return
        
        # Хешируем пароль
        hashed_password = get_password_hash(password)
        
        # Создаем пользователя
        try:
            user = await create_user(
                session,
                username=username,
                email=os.getenv("ADMIN_EMAIL", f"{username}@example.com"),
                hashed_password=hashed_password,
                full_name="Administrator",
                role="admin",
            )
            print(f"Администратор {username} успешно создан!")
            print(f"ID: {user.id}")
        except Exception as e:
            print(f"Ошибка при создании администратора: {e}")

if __name__ == "__main__":
    asyncio.run(create_admin_user())




