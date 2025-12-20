"""
FastAPI микросервис для обработки сообщений через AI агента.
Принимает запросы от Telegram бота и возвращает ответы агента.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import logging
import asyncio
import json

from langchain_core.messages import HumanMessage, AIMessage
from agent import agent
from db.session import async_session_factory
from db.repository import get_or_create_lead, get_or_create_thread, save_message, save_ai_stats

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем FastAPI приложение
app = FastAPI(
    title="AI Consultant Service",
    description="Микросервис для обработки сообщений через AI агента продаж",
    version="0.1.0"
)

# Настройка CORS (если нужно обращаться с фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Модели запросов и ответов
class MessageRequest(BaseModel):
    """Запрос на обработку сообщения."""
    message: str
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    context: Optional[List[dict]] = None  # История сообщений для контекста
    metadata: Optional[dict] = None  # Метаданные пользователя (имя, телефон, канал и т.д.)


class MessageResponse(BaseModel):
    """Ответ от агента."""
    response: str
    user_id: Optional[str] = None
    chat_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Ответ для health check."""
    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", service="ai-consultant")


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
            lead = await get_or_create_lead(
                db_session, 
                channel=channel, 
                external_id=external_id,
                name=metadata.get("first_name"),
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

@app.post("/chat", response_model=MessageResponse)
async def chat(request: MessageRequest):
    """
    Обработка сообщения пользователя через AI агента.
    """
    try:
        logger.info(f"Received message from user {request.user_id}: {request.message[:50]}...")
        
        # Подготовка сообщений для агента
        messages = []
        if request.context:
            for msg in request.context:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))
        
        messages.append(HumanMessage(content=request.message))
        
        # Запуск агента
        result_state = await agent.ainvoke({
            "messages": messages,
            "user_info": request.metadata or {}
        })
        
        # Фоновое логирование в БД (не блокирует ответ клиенту)
        asyncio.create_task(log_interaction(request, result_state))
        
        # Извлечение ответа для клиента
        structured_data = result_state.get("structured_response")
        agent_response = ""
        should_ignore = False

        if structured_data:
            agent_response = getattr(structured_data, "response", "")
            should_ignore = getattr(structured_data, "ignore", False)
        
        agent_response = agent_response.replace("—", "-")
        
        if should_ignore:
            return MessageResponse(response="", user_id=request.user_id, chat_id=request.chat_id)
        
        return MessageResponse(
            response=agent_response,
            user_id=request.user_id,
            chat_id=request.chat_id
        )
    
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5537)

