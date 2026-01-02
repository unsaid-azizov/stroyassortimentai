import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from typing import Annotated, TypedDict, Optional, List, Any
from pydantic import BaseModel, Field
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
import logging
import time

from dotenv import load_dotenv
from os import getenv
import os

# Импортируем tools
from tools import call_manager, collect_order_info, search_1c_products, get_product_details

load_dotenv()

logger = logging.getLogger(__name__)

MAIN_LLM = getenv("MAIN_LLM")
BACKUP_LLM = getenv("BACKUP_LLM")

# Проверяем, не является ли модель моделью с reasoning
if MAIN_LLM and ("o1" in MAIN_LLM.lower() or "o3" in MAIN_LLM.lower() or "gpt-5" in MAIN_LLM.lower()):
    logger.warning(f"⚠️ ВНИМАНИЕ: Модель {MAIN_LLM} может использовать reasoning, что тратит много токенов! "
                  f"Рекомендуется использовать модель без reasoning (например, openai/gpt-4o-mini или openai/gpt-4o)")

llm_config = {
    "temperature": 0.0,
    # api_key is DB-backed (runtime_config). Fallback to env for bootstrap/dev.
    "api_key": None,
    "base_url": getenv("OPENAI_BASE_URL"),
    "timeout": 30,
    "max_retries": 3,
    "reasoning": {
        "effort": "low"
    }
}

def _build_llm_clients(api_key: str | None):
    cfg = dict(llm_config)
    cfg["api_key"] = api_key
    main = ChatOpenAI(model=MAIN_LLM, **cfg)
    backup = ChatOpenAI(model=BACKUP_LLM, **cfg)
    return main, backup


_CURRENT_LLM_API_KEY: Optional[str] = None
main_llm, backup_llm = _build_llm_clients(getenv("OPENAI_API_KEY"))

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
# Runtime-config (DB-backed)
# ==========================

_RUNTIME_PROMPT_TEXT: Optional[str] = None
_RUNTIME_KB_CONTENT: Optional[dict] = None
_RUNTIME_KB_TEXT: Optional[str] = None
_RUNTIME_LAST_REFRESH_TS: float = 0.0


def _format_kb_text(kb_content: Optional[dict]) -> str:
    if not kb_content:
        return ""
    try:
        s = json.dumps(kb_content, ensure_ascii=False, indent=2)
    except Exception:
        s = str(kb_content)
    max_chars = 20000
    if len(s) > max_chars:
        return s[:max_chars] + "\n\n...[KB truncated]..."
    return s


def get_agent_runtime_snapshot() -> dict:
    return {
        "has_prompt": bool(_RUNTIME_PROMPT_TEXT),
        "has_knowledge_base": bool(_RUNTIME_KB_CONTENT),
        "last_refresh_ts": _RUNTIME_LAST_REFRESH_TS,
    }


async def refresh_agent_runtime_config(force: bool = False, ttl_seconds: int = 15) -> None:
    """
    Loads active prompt and knowledge base from DB into in-memory cache.
    Uses TTL to avoid hitting DB on every message.
    """
    global _RUNTIME_PROMPT_TEXT, _RUNTIME_KB_CONTENT, _RUNTIME_KB_TEXT, _RUNTIME_LAST_REFRESH_TS

    now = time.time()
    if (not force) and _RUNTIME_LAST_REFRESH_TS and (now - _RUNTIME_LAST_REFRESH_TS) < ttl_seconds:
        return

    try:
        from db.session import async_session_factory
        from db.repository import get_active_prompt_config, get_settings
    except Exception as e:
        logger.warning(f"Could not import DB helpers for runtime config: {e}")
        return

    async with async_session_factory() as session:
        prompt = await get_active_prompt_config(session)
        if prompt and prompt.content:
            _RUNTIME_PROMPT_TEXT = prompt.content

        kb_settings = await get_settings(session, "knowledge_base")
        if kb_settings and kb_settings.value:
            _RUNTIME_KB_CONTENT = kb_settings.value
            _RUNTIME_KB_TEXT = _format_kb_text(_RUNTIME_KB_CONTENT)

    # Refresh secrets via runtime_config and rebuild LLM/agent if token changed
    try:
        from runtime_config import refresh_runtime_config, get_secret_cached
        await refresh_runtime_config(force=force, ttl_seconds=ttl_seconds)
        new_key = get_secret_cached("openrouter_token") or getenv("OPENAI_API_KEY")
        global _CURRENT_LLM_API_KEY, main_llm, backup_llm, agent, agent_backup
        if new_key and new_key != _CURRENT_LLM_API_KEY:
            _CURRENT_LLM_API_KEY = new_key
            # also set env for libs that may read it implicitly
            os.environ["OPENAI_API_KEY"] = new_key
            main_llm, backup_llm = _build_llm_clients(new_key)
            # Rebuild agent so it uses the refreshed model
            agent = create_react_agent(
                model=main_llm,
                tools=agent_tools,
                prompt=dynamic_prompt_template,
                state_schema=AgentState,
                response_format=AgentStructuredResponse,
            )
            agent_backup = create_react_agent(
                model=backup_llm,
                tools=agent_tools,
                prompt=dynamic_prompt_template,
                state_schema=AgentState,
                response_format=AgentStructuredResponse,
            )
    except Exception as e:
        logger.warning(f"Could not refresh secrets/LLM from DB: {e}")

    _RUNTIME_LAST_REFRESH_TS = now


def _fallback_kb_from_files() -> str:
    info_path = Path(__file__).parent / "data" / "company_info.json"
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return _format_kb_text(json.load(f))
    except FileNotFoundError:
        return ""


def _get_prompt_base() -> str:
    if _RUNTIME_PROMPT_TEXT:
        return _RUNTIME_PROMPT_TEXT
    return "Ты — Саид, менеджер по продажам «СтройАссортимент». Отвечай только по товарам/ценам/наличию/доставке/оплате и контактам компании."


def _get_kb_text() -> str:
    if _RUNTIME_KB_TEXT:
        return _RUNTIME_KB_TEXT
    return _fallback_kb_from_files()


def dynamic_prompt_template(state: AgentState) -> list[BaseMessage]:
    """Dynamic prompt template for the agent."""
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
    
    system_prompt = (
        _get_prompt_base()
        + f"\n\nКОНТЕКСТ КЛИЕНТА: {user_name} ({user_phone}), канал: {channel}. Сейчас {current_time_str}, {weekday_ru}."
        + "\n\nБАЗА ЗНАНИЙ (из БД):\n"
        + _get_kb_text()
    )

    # Возвращаем список сообщений: системное + вся история из state
    return [SystemMessage(content=system_prompt)] + state["messages"]

def load_merged_text() -> str:
    """Legacy helper (kept for backward compatibility)."""
    return _get_kb_text()


# Backward-compatibility: ai_service.py imports this symbol.
def load_company_info() -> dict:
    """Load company information from JSON file (legacy helper)."""
    info_path = Path(__file__).parent / "data" / "company_info.json"
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

agent_tools = [
    call_manager,
    collect_order_info,
    search_1c_products,
    get_product_details,
]

# Создаем агента с использованием langgraph.prebuilt.create_react_agent
# Мы используем prompt для динамического системного промпта и state_schema для метаданных
# response_format заставляет агента всегда возвращать структурированный JSON
agent = create_react_agent(
    model=main_llm,
    tools=agent_tools,
    prompt=dynamic_prompt_template,
    state_schema=AgentState,
    response_format=AgentStructuredResponse,
)

agent_backup = create_react_agent(
    model=backup_llm,
    tools=agent_tools,
    prompt=dynamic_prompt_template,
    state_schema=AgentState,
    response_format=AgentStructuredResponse,
)


def build_retry_agent(temperature: float):
    """
    Build a temporary structured agent with a different temperature for retry attempts.
    Avoids any "parse from text" fallbacks; still uses response_format.
    """
    cfg = dict(llm_config)
    cfg["temperature"] = float(temperature)
    cfg["api_key"] = _CURRENT_LLM_API_KEY or getenv("OPENAI_API_KEY")
    temp_llm = ChatOpenAI(model=MAIN_LLM, **cfg)
    return create_react_agent(
        model=temp_llm,
        tools=agent_tools,
        prompt=dynamic_prompt_template,
        state_schema=AgentState,
        response_format=AgentStructuredResponse,
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
