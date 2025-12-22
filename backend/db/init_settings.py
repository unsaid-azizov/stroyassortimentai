"""
Скрипт для заполнения БД настройками из переменных окружения.
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Пытаемся загрузить .env из разных мест
env_paths = [
    Path("/app/.env"),  # В контейнере
    Path(__file__).parent.parent.parent / ".env",  # Рядом с проектом
    Path.home() / ".env",  # Домашняя директория
]

for env_path in env_paths:
    if env_path.exists():
        print(f"Загрузка .env из {env_path}")
        load_dotenv(env_path)
        break
else:
    # Если файл не найден, загружаем из текущей директории
    load_dotenv()

from db.session import async_session_factory
from db.repository import upsert_settings

async def init_settings():
    """Заполняет БД настройками из .env."""
    print("Заполнение настроек из .env...")
    
    async with async_session_factory() as session:
        # Функция для получения значения с удалением кавычек
        def get_env_value(key: str, default: str = None) -> str:
            value = os.getenv(key, default)
            if value and isinstance(value, str):
                # Удаляем кавычки в начале и конце, если есть
                value = value.strip().strip('"').strip("'")
            return value if value else None
        
        settings_dict = {
            "openrouter_token": get_env_value("OPENAI_API_KEY"),
            "telegram_bot_token": get_env_value("BOT_TOKEN"),
            "smtp_user": get_env_value("SMTP_USER"),
            "smtp_password": get_env_value("SMTP_PASSWORD"),
            "sales_email": get_env_value("SALES_EMAIL"),
            "imap_server": get_env_value("IMAP_SERVER", "imap.gmail.com"),
            "smtp_server": get_env_value("SMTP_SERVER", "smtp.gmail.com"),
        }
        
        # Обрабатываем порты отдельно
        imap_port_str = get_env_value("IMAP_PORT", "993")
        if imap_port_str:
            try:
                settings_dict["imap_port"] = int(imap_port_str)
            except ValueError:
                settings_dict["imap_port"] = 993
        
        smtp_port_str = get_env_value("SMTP_PORT", "587")
        if smtp_port_str:
            try:
                settings_dict["smtp_port"] = int(smtp_port_str)
            except ValueError:
                settings_dict["smtp_port"] = 587
        
        # Удаляем None значения
        settings_dict = {k: v for k, v in settings_dict.items() if v is not None}
        
        await upsert_settings(session, "system", settings_dict)
        print("✅ Настройки успешно сохранены в БД!")
        print(f"   - OpenRouter токен: {'✓' if settings_dict.get('openrouter_token') else '✗'}")
        print(f"   - Telegram Bot токен: {'✓' if settings_dict.get('telegram_bot_token') else '✗'}")
        print(f"   - Gmail настройки: {'✓' if settings_dict.get('smtp_user') else '✗'}")

if __name__ == "__main__":
    asyncio.run(init_settings())

