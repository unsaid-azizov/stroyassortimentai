import asyncio
import sys
import os

# Добавляем корневую директорию в путь, чтобы импорты работали
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import engine
from db.models import Base, User  # Импортируем User, чтобы таблица создалась

async def init_db():
    print("Создание таблиц в базе данных...")
    async with engine.begin() as conn:
        # Для отладки можно расскомментировать следующую строку, чтобы пересоздавать таблицы
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Таблицы успешно созданы.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())

