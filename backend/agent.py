import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from typing import Annotated, TypedDict, Optional, List, Any
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware.types import dynamic_prompt, ModelRequest
from langchain.agents.middleware import SummarizationMiddleware
import logging
import time

from dotenv import load_dotenv
from os import getenv
import os

# Импортируем tools
from tools import search_company_info, call_manager, collect_order_info, search_products_tool, get_product_live_details
from params_manager import ParamsManager

load_dotenv()

# Создаем глобальный инстанс ParamsManager (singleton)
params_manager = ParamsManager()

logger = logging.getLogger(__name__)

MAIN_LLM = getenv("MAIN_LLM")
BACKUP_LLM = getenv("BACKUP_LLM")

llm_config = {
    "temperature": 0.0,
    # api_key is DB-backed (runtime_config). Fallback to env for bootstrap/dev.
    "api_key": None,
    "base_url": getenv("OPENAI_BASE_URL"),
    "timeout": 30,
    "max_retries": 3,
    "reasoning": {
        "effort": "low"
    },
}

backup_llm = ChatOpenAI(model=BACKUP_LLM, **llm_config)
main_llm = ChatOpenAI(model=MAIN_LLM, **llm_config).with_fallbacks([backup_llm])

# Model for summarization (use cheaper/faster model for summarization tasks)
# Use backup_llm or a dedicated summarization model
summarization_llm = ChatOpenAI(
    model=BACKUP_LLM,  # Use backup model for summarization (usually cheaper)
    temperature=0.0,
    base_url=getenv("OPENAI_BASE_URL"),
    timeout=30,
    max_retries=3,
)

# Модель структурированного ответа для классификации и ответа клиенту
class AgentStructuredResponse(BaseModel):
    category: str = Field(description="Категория сообщения: SPAM, ORDER_LEAD, COMPANY_INFO, DELIVERY_PAYMENT, SMALL_TALK, OFF_TOPIC, HUMAN_NEEDED")
    reasoning: str = Field(description="Краткое обоснование выбора категории")
    response: str = Field(description="Твой ответ клиенту. Если category=SPAM или OFF_TOPIC, может быть пустой строкой или кратким отказом.")
    ignore: bool = Field(description="true если сообщение - спам или не по теме, и отвечать клиенту НЕ нужно. false в остальных случаях.")

# Определяем схему состояния агента
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_info: dict
    remaining_steps: int
    structured_response: Optional[AgentStructuredResponse]


# ==========================
# Dynamic Prompt Middleware
# ==========================

@dynamic_prompt
def build_agent_prompt(req: ModelRequest) -> str:
    """
    Dynamic prompt builder for the agent using @dynamic_prompt middleware.
    Gets prompt and KB from ParamsManager (sync getters).
    """
    state = req.state
    
    # Устанавливаем часовой пояс МСК (UTC+3)
    current_time = datetime.now(ZoneInfo("Europe/Moscow"))
    current_time_str = current_time.strftime("%H:%M")
    weekday = current_time.strftime("%A")
    weekday_ru = {
        "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
        "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    }.get(weekday, weekday)
    
    # Извлекаем метаданные пользователя для персонализации
    user_info = state.get("user_info", {})
    user_name = user_info.get("first_name", user_info.get("username", "Клиент"))
    user_phone = user_info.get("phone", "не указан")
    channel = user_info.get("channel", "неизвестный канал")
    
    # Get prompt and KB from global ParamsManager instance (sync getters)
    prompt_base = params_manager.get_prompt()
    kb_text = params_manager.get_knowledge_base_text()  # Компактный формат (только справочник разделов и кодов групп)
    
    system_prompt = (
        prompt_base
        + f"\n\nКОНТЕКСТ КЛИЕНТА: {user_name} ({user_phone}), канал: {channel}. Сейчас {current_time_str}, {weekday_ru}."
        + "\n\nСПРАВОЧНИК БАЗЫ ЗНАНИЙ (детальная информация доступна через search_company_info):\n"
        + kb_text
        + "\n\nВАЖНО: Для получения детальной информации используй инструмент search_company_info с нужным разделом."
        + " Не выдумывай данные - всегда запрашивай их через инструменты!"
    )
    
    return system_prompt

# Backward-compatibility: api.py imports this symbol.
def load_company_info() -> dict:
    """Load company information from KB."""
    return params_manager.get_knowledge_base_dict()

agent_tools = [
    search_company_info,
    call_manager,
    collect_order_info,
    search_products_tool,  # BM25 product search (offline CSV)
    get_product_live_details,  # Live data from 1C API
]

# SummarizationMiddleware для автоматического сжатия контекста при превышении лимита токенов
# Суммаризирует старые сообщения, сохраняя последние N сообщений
summarization_middleware = SummarizationMiddleware(
    model=summarization_llm,
    trigger=("tokens", 6000),  # Суммаризировать когда превышено 6000 токенов
    keep=("messages", 20),  # Сохранять последние 20 сообщений без суммаризации
)

# Middleware stack: сначала промпт, потом суммаризация
middleware_stack = [
    build_agent_prompt,  # Dynamic prompt middleware
    summarization_middleware,  # Automatic context compression
]

agent = create_agent(
    model=main_llm,
    tools=agent_tools,
    state_schema=AgentState,
    response_format=AgentStructuredResponse,
    middleware=middleware_stack,
)

# Backup agent (uses backup_llm with fallback)
agent_backup = create_agent(
    model=backup_llm,
    tools=agent_tools,
    state_schema=AgentState,
    response_format=AgentStructuredResponse,
    middleware=middleware_stack,
)

def build_retry_agent(temperature: float):
    """
    Build a temporary structured agent with a different temperature for retry attempts.
    Avoids any "parse from text" fallbacks; still uses response_format.
    """
    cfg = dict(llm_config)
    cfg["temperature"] = float(temperature)
    cfg["api_key"] = getenv("OPENAI_API_KEY")
    temp_llm = ChatOpenAI(model=MAIN_LLM, **cfg)
    return create_agent(
        model=temp_llm,
        tools=agent_tools,
        state_schema=AgentState,
        response_format=AgentStructuredResponse,
        middleware=middleware_stack,  # Use same middleware stack
    )


async def main():
    while True: 
        query = input("> ")
        if query.lower() == "/exit": 
            break

        # Используем astream для поддержки асинхронных инструментов
        async for step in agent.astream(
            {"messages": [HumanMessage(content=query)]},
            stream_mode="values"
        ):
            step["messages"][-1].pretty_print()

if __name__ == "__main__": 
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
