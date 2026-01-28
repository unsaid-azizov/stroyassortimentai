"""
FastAPI микросервис для обработки сообщений через AI агента.
Принимает запросы от Telegram бота и возвращает ответы агента.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import asyncio
from pydantic import ValidationError

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.load import dumpd, load
import agent as agent_module
from params_manager import ParamsManager
from typing import List

# Создаем глобальный инстанс ParamsManager (singleton)
params_manager = ParamsManager()

from db.session import async_session_factory
from db.repository import (
    get_or_create_lead, 
    get_or_create_thread, 
    save_message, 
    save_ai_stats,
)
from schemas.service_schemas import (
    MessageRequest,
    MessageResponse,
    HealthResponse,
)
# Настройка логирования
from utils.logger import setup_logging
logger = setup_logging("api")

# Создаем роутер для AI эндпоинтов
router = APIRouter()


async def log_interaction(request: MessageRequest, result_state: dict):
    """
    Фоновое логирование взаимодействия в БД PostgreSQL.
    """
    async with async_session_factory() as db_session:
        try:
            metadata = request.metadata or {}
            channel = metadata.get("channel", "unknown")
            external_id = request.user_id or request.chat_id or "unknown"

            # 1. Лид и Тред
            # Формируем полное имя из first_name и last_name
            first_name = metadata.get("first_name", "")
            last_name = metadata.get("last_name", "")
            full_name = " ".join(filter(None, [first_name, last_name])) or None

            lead = await get_or_create_lead(
                db_session,
                channel=channel,
                external_id=external_id,
                username=metadata.get("username"),
                name=full_name,
                phone=metadata.get("phone"),
                email=metadata.get("email")
            )
            thread = await get_or_create_thread(db_session, lead.id)

            # 2. Сообщение пользователя
            await save_message(db_session, thread.id, "USER", request.message)

            # 3. Данные ответа Бота
            structured_data = result_state.get("structured_response")
            if structured_data:
                category = getattr(structured_data, "category", "UNKNOWN")
                reasoning = getattr(structured_data, "reasoning", "")
                agent_response = getattr(structured_data, "response", "")
                should_ignore = getattr(structured_data, "ignore", False)

                # Сохраняем ответ ИИ
                ai_msg = await save_message(
                    db_session,
                    thread_id=thread.id,
                    sender_role="AI",
                    content=agent_response if not should_ignore else "[IGNORED]"
                )
                
                # Сохраняем детальную статистику
                await save_ai_stats(
                    db_session,
                    message_id=ai_msg.id,
                    category=category,
                    reasoning=reasoning,
                    ignored=should_ignore,
                    model_name="gpt-4o-mini"
                )
        except Exception as e:
            logger.error(f"Error in log_interaction: {e}")

@router.post("/chat", response_model=MessageResponse)
async def chat(request: MessageRequest):
    """
    Обработка сообщения пользователя через AI агента.
    """
    logger.info(f"Received message from user {request.user_id}: {request.message[:50]}...")

    # Refresh params if needed (checks versions, updates only if changed)
    await params_manager.refresh_if_needed()

    # Подготовка сообщений для агента
    # Десериализуем контекст из формата словарей в объекты LangChain используя native LangChain load()
    messages = []
    if request.context:
        for msg_dict in request.context:
            if isinstance(msg_dict, dict) and "lc" in msg_dict:
                msg = load(msg_dict)
                if isinstance(msg, BaseMessage) and not isinstance(msg, SystemMessage):
                    messages.append(msg)

    # Добавляем новое сообщение пользователя
    messages.append(HumanMessage(content=request.message))

    # Вызов агента (fallback уже встроен в main_llm через .with_fallbacks())
    # Просто передаем metadata как есть: bot -> api -> agent
    try:
        result_state = await asyncio.wait_for(
            agent_module.get_agent().ainvoke(
                {
                    "messages": messages,
                    "user_info": request.metadata or {}
                },
                config={"configurable": {"user_info": request.metadata or {}}}
            ),
            timeout=180.0
        )
    except asyncio.TimeoutError:
        logger.warning(f"Request timeout for user {request.user_id}")
        raise HTTPException(
            status_code=504,
            detail="Request timeout. Please try again."
        )
    
    # Фоновое логирование в БД (не блокирует ответ клиенту)
    asyncio.create_task(log_interaction(request, result_state))
    
    # Сериализуем полную историю сообщений из result_state (включая ToolMessage)
    # Используем native LangChain dumpd() для сериализации
    all_messages = result_state["messages"]
    updated_context = [
        dumpd(msg) for msg in all_messages 
        if isinstance(msg, BaseMessage) and not isinstance(msg, SystemMessage)
    ]
    
    # Извлечение ответа для клиента
    structured_data = result_state["structured_response"]
    agent_response = structured_data.response.replace("—", "-")
    
    if structured_data.ignore:
        return MessageResponse(
            response="",
            user_id=request.user_id,
            chat_id=request.chat_id,
            updated_context=updated_context,
            ignored=True,
            category=structured_data.category,
            reasoning=structured_data.reasoning,
        )
    
    return MessageResponse(
        response=agent_response,
        user_id=request.user_id,
        chat_id=request.chat_id,
        updated_context=updated_context,
        ignored=False,
        category=structured_data.category,
        reasoning=structured_data.reasoning,
    )
