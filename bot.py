"""
Telegram бот для консультанта по продажам.
Подключается к FastAPI микросервису для обработки сообщений через AI агента.
"""
import asyncio
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

import httpx
import logging

from dotenv import load_dotenv
from os import getenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = getenv("BOT_TOKEN")
AI_SERVICE_URL = getenv("AI_SERVICE_URL", "http://localhost:5537")

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище контекста диалогов (в продакшене использовать Redis или БД)
user_contexts: Dict[int, List[Dict[str, str]]] = {}


async def get_ai_response(message_text: str, user_id: int, chat_id: int, metadata: Optional[dict] = None) -> str:
    """
    Отправляет запрос в AI сервис и получает ответ.
    
    Args:
        message_text: Текст сообщения пользователя
        user_id: ID пользователя
        chat_id: ID чата
        metadata: Данные профиля пользователя
    
    Returns:
        Ответ от AI агента
    """
    try:
        # Получаем контекст диалога для пользователя
        context = user_contexts.get(user_id, [])
        
        # Формируем запрос
        request_data = {
            "message": message_text,
            "user_id": str(user_id),
            "chat_id": str(chat_id),
            "context": context,
            "metadata": metadata
        }
        
        # Отправляем запрос в AI сервис
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_SERVICE_URL}/chat",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Обновляем контекст диалога
            context.append({"role": "user", "content": message_text})
            context.append({"role": "assistant", "content": result["response"]})
            
            # Ограничиваем размер контекста (последние 10 сообщений)
            if len(context) > 20:  # 10 пар вопрос-ответ
                context = context[-20:]
            
            user_contexts[user_id] = context
            
            return result["response"]
    
    except httpx.TimeoutException:
        logger.error(f"Timeout when calling AI service for user {user_id}")
        return "Извините, сервис временно недоступен. Попробуйте позже."
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error when calling AI service: {e.response.status_code}")
        return "Произошла ошибка при обработке запроса. Попробуйте позже."
    
    except Exception as e:
        logger.error(f"Error calling AI service: {str(e)}", exc_info=True)
        return "Произошла внутренняя ошибка. Пожалуйста, попробуйте позже или обратитесь в поддержку."


@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    """Обработчик команды /start"""
    welcome_text = (
        "👋 Здравствуйте! Я виртуальный консультант компании <b>СтройАссортимент</b>.\n\n"
        "Я помогу вам:\n"
        "• Подобрать строительные материалы\n"
        "• Узнать о доставке и оплате\n"
        "• Ответить на вопросы о товарах\n"
        "• Предоставить контактную информацию\n\n"
        "Просто напишите ваш вопрос, и я постараюсь помочь! 😊"
    )
    await message.answer(welcome_text, parse_mode="HTML")
    
    # Очищаем контекст при новом старте
    if message.from_user:
        user_contexts.pop(message.from_user.id, None)


@dp.message(Command("clear"))
async def command_clear_handler(message: Message) -> None:
    """Обработчик команды /clear - очистка контекста диалога"""
    if message.from_user:
        user_contexts.pop(message.from_user.id, None)
        await message.answer("✅ Контекст диалога очищен. Можем начать заново!", parse_mode="HTML")
    else:
        await message.answer("Не удалось определить пользователя.", parse_mode="HTML")


@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    """Обработчик команды /help"""
    help_text = (
        "📋 <b>Доступные команды:</b>\n\n"
        "/start - Начать диалог\n"
        "/clear - Очистить историю диалога\n"
        "/help - Показать эту справку\n\n"
        "Просто напишите ваш вопрос, и я помогу вам с выбором товаров, "
        "информацией о доставке, оплате и других вопросах!"
    )
    await message.answer(help_text, parse_mode="HTML")


@dp.message()
async def handle_message(message: Message) -> None:
    """Обработчик всех текстовых сообщений"""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return
    
    if not message.from_user:
        await message.answer("Не удалось определить пользователя.")
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Собираем метаданные пользователя для персонализации
    user = message.from_user
    metadata = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "language_code": user.language_code,
        "channel": "telegram"
    }
    
    # Показываем индикатор печати
    await bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # Получаем ответ от AI сервиса
        # Мы можем расширить get_ai_response для приема метаданных
        response = await get_ai_response(
            message_text=message.text,
            user_id=user_id,
            chat_id=chat_id,
            metadata=metadata
        )
        
        # Отправляем ответ пользователю
        await message.answer(response, parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке вашего сообщения. "
            "Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )


async def check_ai_service_health() -> bool:
    """Проверяет доступность AI сервиса"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{AI_SERVICE_URL}/health")
            return response.status_code == 200
    except Exception:
        return False


async def on_startup():
    """Выполняется при запуске бота"""
    logger.info("Bot is starting...")
    
    # Проверяем доступность AI сервиса
    if await check_ai_service_health():
        logger.info(f"AI service is available at {AI_SERVICE_URL}")
    else:
        logger.warning(f"AI service is not available at {AI_SERVICE_URL}. Bot will still start but may fail.")


async def on_shutdown():
    """Выполняется при остановке бота"""
    logger.info("Bot is shutting down...")


async def main() -> None:
    """Главная функция запуска бота"""
    # Регистрируем обработчики событий
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Запускаем бота
    logger.info("Starting bot...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
