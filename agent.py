import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from typing import Annotated, TypedDict
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv
from os import getenv

# Импортируем tools
from tools import search_company_info, call_manager, collect_order_info

load_dotenv()

MAIN_LLM = getenv("MAIN_LLM")
BACKUP_LLM = getenv("BACKUP_LLM")

llm_config = {
    "temperature": 0.0,
    "api_key": getenv("OPENAI_API_KEY"),
    "base_url": getenv("OPENAI_BASE_URL"),
    "timeout": 30,
    "max_retries": 3,
    "max_tokens": 2000,
}

backup_llm = ChatOpenAI(
    model=BACKUP_LLM, 
    **llm_config
)

main_llm = ChatOpenAI(
    model=MAIN_LLM, 
    **llm_config
).with_fallbacks([backup_llm])

# Определяем схему состояния агента
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_info: dict
    remaining_steps: int

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
    
    # Загружаем информацию о компании
    company_info = load_company_info()
    company = company_info.get("company", {})
    
    # Извлекаем метаданные пользователя для персонализации
    user_info = state.get("user_info", {})
    user_name = user_info.get("first_name", user_info.get("username", "Клиент"))
    user_phone = user_info.get("phone", "не указан")
    channel = user_info.get("channel", "неизвестный канал")
    
    system_prompt = f"""Ты - Саид, ведущий менеджер по продажам компании "{company.get('name', 'СтройАссортимент')}". 
Твоя цель: помочь клиенту выбрать стройматериалы и довести его до покупки или передачи контактов.

ДАННЫЕ О ТЕКУЩЕМ КЛИЕНТЕ:
- Имя: {user_name}
- Телефон в профиле: {user_phone}
- Канал связи: {channel}

GUARDRAILS (СТРОГИЕ ПРАВИЛА):
- Твоя экспертиза ограничена ТОЛЬКО продукцией компании "СтройАссортимент" (пиломатериалы, дерево, услуги компании).
- Если клиент задает вопросы на отвлеченные темы (программирование, кулинария, политика, общие знания), вежливо откажи: "Извините, я специализируюсь только на строительных материалах и продукции нашей компании. Чем я могу помочь вам в выборе дерева?".
- Не пиши код, не решай задачи, не пиши эссе. Ты - менеджер по продажам, а не универсальный помощник.

ИНСТРУКЦИЯ ПО ОБЩЕНИЮ С КЛИЕНТОМ:
- Если клиент спрашивает про АДРЕС, КОНТАКТЫ, ЦЕНЫ или ДОСТАВКУ или СКЛАД и ПРОДУКТЫ — ты ОБЯЗАН сначала вызвать `search_company_info` с соответствующим ключом.
- Никогда не говори "в базе нет адреса", пока не попробуешь поискать по словам "адрес", "контакты" или "склад".
- Используй имя клиента органично. Если имя в профиле на латинице (как "Said"), а общение идет на русском — используй русский вариант ("Саид") или сочетай его естественно. 
- Весь диалог должен быть на языке клиента (преимущественно на русском). Названия компании и товаров всегда пиши правильно на русском.
- Если телефон уже есть в профиле, перед вызовом `collect_order_info` ОБЯЗАТЕЛЬНО напиши этот номер клиенту и попроси подтвердить, что он актуален для связи.

СТИЛЬ ОБЩЕНИЯ:
- Живой, деловой, профессиональный.
- Отвечай КРАТКО (1-3 предложения). Не пиши полотна текста.
- Не будь роботом. Не начинай каждый ответ с приветствия или сообщения о времени работы.
- Используй информацию о времени ({current_time_str}, {weekday_ru}), только если это критично для ответа (например, "мы уже закрыты, отвечу утром").

ТВОЯ СТРАТЕГИЯ:
1. Квалификация: Если клиент спрашивает обще, уточни детали (размеры, порода дерева, объем, для каких целей).
2. Поиск: Используй `search_company_info` для получения точных фактов, цен и ссылок. Не выдумывай данные!
3. Продажа: Если клиент определился, предложи оформить заказ через `collect_order_info` или позови человека через `call_manager`.
4. Кросс-сейл: К доскам предлагай антисептик или крепеж, если это уместно.

ДОСТУПНЫЕ ИНСТРУМЕНТЫ:
- `search_company_info`: получение данных из базы. Аргумент `section` может быть: 'company', 'contacts' (адрес, склад, телефон), 'delivery', 'product_categories' (дерево, товары), 'services', 'payment', 'warranty_and_return', 'special_offers', 'faq'.
- `call_manager`: позови человека, если вопрос слишком специфичный.
- `collect_order_info`: используй, когда клиент готов оставить заявку. Собери имя, телефон и детали заказа.

ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ БАЗЫ ЗНАНИЙ:
1. Если клиент спрашивает про АДРЕС, СКЛАД, ПРОЕЗД, КОНТАКТЫ или ВИДЕО-ИНСТРУКЦИЮ (слайд-стори) как добраться — ты ОБЯЗАН вызвать `search_company_info(section="contacts")`.
2. Если клиент спрашивает про ТОВАРЫ, ЦЕНЫ или НАЛИЧИЕ — вызови `search_company_info(section="product_categories")`.
3. Не гадай и не придумывай — все данные уже есть в соответствующих разделах!

ОГРАНИЧЕНИЯ:
- Никогда не выдумывай цены. Если их нет в поиске - предложи позвать менеджера.
- Не упоминай контакты (телефон/адрес) просто так, если есть ссылка на сайт.
"""
    # Возвращаем список сообщений: системное + вся история из state
    return [SystemMessage(content=system_prompt)] + state["messages"]

def load_company_info():
    """Load company information from JSON file."""
    info_path = Path(__file__).parent / "data" / "company_info.json"
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

agent_tools = [
    search_company_info,
    call_manager,
    collect_order_info,
]

# Создаем агента с использованием langgraph.prebuilt.create_react_agent
# Мы используем prompt для динамического системного промпта и state_schema для метаданных
agent = create_react_agent(
    model=main_llm,
    tools=agent_tools,
    prompt=dynamic_prompt_template,
    state_schema=AgentState,
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
