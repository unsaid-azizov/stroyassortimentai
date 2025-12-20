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


@app.post("/chat", response_model=MessageResponse)
async def chat(request: MessageRequest):
    """
    Обработка сообщения пользователя через AI агента.
    
    Args:
        request: Запрос с сообщением пользователя и опциональным контекстом
    
    Returns:
        Ответ от агента
    """
    try:
        logger.info(f"Received message from user {request.user_id}: {request.message[:50]}...")
        logger.info(f"Metadata: {request.metadata}")
        
        # Формируем сообщения для агента
        messages = []
        
        # Системный промпт уже добавляется через middleware в агенте
        # Но можно добавить дополнительный контекст если нужно
        
        # Добавляем контекст из истории, если есть
        if request.context:
            for msg in request.context:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))
        
        # Добавляем текущее сообщение пользователя
        messages.append(HumanMessage(content=request.message))
        
        # Запускаем агента
        # Передаем сообщения и метаданные пользователя в стейт
        response = await agent.ainvoke({
            "messages": messages,
            "user_info": request.metadata or {}
        })
        
        # Извлекаем ответ от агента
        # Агент возвращает словарь с ключом "messages", последнее сообщение - ответ агента
        agent_messages = response.get("messages", [])
        if not agent_messages:
            raise HTTPException(status_code=500, detail="Agent returned empty response")
        
        # Берем последнее сообщение (ответ агента)
        last_message = agent_messages[-1]
        agent_response = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # Очистка текста: заменяем длинное тире на обычное
        agent_response = agent_response.replace("—", "-")
        
        logger.info(f"Agent response generated for user {request.user_id}")
        
        return MessageResponse(
            response=agent_response,
            user_id=request.user_id,
            chat_id=request.chat_id
        )
    
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5537)

