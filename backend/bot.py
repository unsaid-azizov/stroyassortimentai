"""
Telegram бот для консультанта по продажам.
Подключается к FastAPI микросервису для обработки сообщений через AI агента.
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from chatgpt_md_converter import telegram_format
from utils.logger import setup_logging
from dotenv import load_dotenv
from os import getenv
import httpx
from ai_service import MessageResponse, MessageRequest

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatAction

logger = setup_logging("bot")
load_dotenv()

# Конфигурация
TOKEN = getenv("BOT_TOKEN")
AI_SERVICE_URL = getenv("AI_SERVICE_URL", "http://localhost:5537")

# Хранилище контекста диалогов (в продакшене использовать Redis или БД)
storage = RedisStorage.from_url(getenv("REDIS_URL"))
# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)


async def send_typing_with_event(
    bot: Bot, 
    chat_id: int, 
    stop_event: asyncio.Event,
    period: int = 5
) -> None:
    while not stop_event.is_set(): 
        try: 
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(period)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error when sending typing action for chat {chat_id}: {e}")
            break

async def ai_request(
    message_text: str, 
    user_id: int, 
    chat_id: int, 
    context: List[dict],
    metadata: Optional[dict] = None
    ) -> MessageResponse:
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
        # Формируем запрос
        request = MessageRequest(
            message=message_text,
            user_id=str(user_id),
            chat_id=str(chat_id),
            context=context,
            metadata=metadata
        )
        
        # Отправляем запрос в AI сервис
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{AI_SERVICE_URL}/chat",
                json=request.model_dump()
            )
            response.raise_for_status()
            logger.info(f"AI service response: \n{response}")
            result = MessageResponse.model_validate(response.json())
            return result
    
    except Exception as e:
        logger.error(f"Error when calling AI service for user {user_id}: {e}")
        return MessageResponse(response="Извините, сервис временно недоступен. Попробуйте позже.")


@dp.message(Command("start"))
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start"""
    welcome_text = (
        "Здравствуйте! Я ИИ-ассистент компании *СтройАссортимент*\n\n"
        "Я могу помочь вам: \n"
        "✅ Подобрать строительные материалы по вашим требованиям \n"
        "✅ Оформить заказ прямо здесь в чате \n"
        "✅ Ответить на вопросы о товарах, доставке и оплате \n"
        "✅ Связать вас с живым менеджером, если нужна консультация \n"
        "📦 Основные категории: \n"
        "• Пиломатериалы \n"
        "• Листовые материалы \n"
        "• Изоляционные материалы \n"
        "• Метизы и антисептики \n"
        "🏭 Собственное производство • 🚚 Доставка по Москве и МО \n"
        "📞 Контакты: \n"
        "Телефон: +7 (499) 302-55-01 \n"
        "Email: info@stroyassortiment.ru \n"
        "Режим работы: Ежедневно с 8:00 до 19:00 \n"
        "💬 Просто напишите, что вас интересует, и я помогу! \n"
    )
    welcome_text = telegram_format(welcome_text)
    await message.answer(welcome_text, parse_mode="HTML")  

    data = await state.get_data()
    await state.update_data(
        processing_message_id=None,
        user_id=message.from_user.id, 
        chat_id=message.chat.id, 
        context=[],
        metadata={
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "username": message.from_user.username,
            "language_code": message.from_user.language_code,
            "channel": "telegram"
        }
    )

@dp.message(Command("clear"))
async def command_clear_handler(message: Message, state: FSMContext) -> None:
    """Обработчик команды /clear - очистка контекста диалога"""
    await state.clear()
    await message.reply("✅ Контекст диалога очищен. Можем начать заново!", parse_mode="HTML")

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
    await message.reply(help_text, parse_mode="HTML")


@dp.message()
async def handle_message(message: Message, state: FSMContext) -> None:
    """Обработчик всех текстовых сообщений"""
    try:
        data = await state.get_data()

        # Если пользователь уже обрабатывается, отправляем сообщение о том, что мы уже обрабатываем его сообщение
        if data.get("processing_message_id"):
            await message.reply(
                "Я уже обрабатываю вот это сообщение. Отправьте его снова после того, как я закончу с вашим текущим сообщением.", 
                parse_mode="HTML",
                reply_to_message_id=data.get("processing_message_id")
            )
            return
        
        # Обновляем состояние для отслеживания текущего сообщения
        await state.update_data(
            processing_message_id=message.message_id,
        ) 

        # Запускаем процесс отправки сообщения "печатается..."
        stop_typing_event = asyncio.Event()
        typing_task = None

        # Если пользователь не отправил текст, отправляем сообщение о том, что нужно отправить текст
        if not message.text:
            await message.answer("Пожалуйста, отправьте текстовое сообщение.")
            return
        
        if not message.from_user:
            await message.answer("Не удалось определить пользователя.")
            return
        
        # Собираем метаданные пользователя для персонализации
        user = message.from_user
        user_id = user.id
        chat_id = message.chat.id
        metadata = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "language_code": user.language_code,
            "channel": "telegram"
        }


        # Запускаем процесс отправки сообщения "печатается..."
        typing_task = asyncio.create_task(send_typing_with_event(bot, chat_id, stop_typing_event))

        # Собираем контекст для отправки в AI сервис
        context = data.get("context", [])

        # Отправляем запрос в AI сервис и получаем ответ
        response = await ai_request(message.text, user_id, chat_id, context, metadata)

        # Используем обновленный контекст из ответа (включая ToolMessage)
        # Если updated_context есть в ответе, используем его, иначе fallback на старый способ
        if response.updated_context:
            updated_context = response.updated_context
        else:
            # Fallback для обратной совместимости
            updated_context = context or []
            updated_context.append({"type": "human", "content": message.text})
            if response.response:
                updated_context.append({"type": "ai", "content": response.response})

        # Обновляем контекст для следующего сообщения
        await state.update_data(
            context=updated_context,
            metadata=metadata
        )

        # Останавливаем процесс отправки сообщения "печатается..."
        stop_typing_event.set()
        if typing_task:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

        # Отправляем ответ пользователю
        await message.reply(response.response, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error when handling message for user {user_id}: {e}")
        # останавливаем процесс отправки сообщения "печатается..."
        stop_typing_event.set()
        if typing_task:
            typing_task.cancel()
        await message.reply("Извините, произошла ошибка. Попробуйте позже.")
    finally:
        await state.update_data(
            processing_message_id=None,
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
