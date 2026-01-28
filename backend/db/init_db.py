import asyncio
import sys
import os

# Добавляем корневую директорию в путь, чтобы импорты работали
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import async_session_factory, engine
from db.models import Base, User, Settings, PromptConfig  # Импортируем все модели, чтобы таблицы создались
from db.repository import get_active_prompt_config, create_prompt_config, get_settings, upsert_settings
from sqlalchemy import select, text
import json
from pathlib import Path

# Дефолтный промпт (из agent.py)
DEFAULT_PROMPT = """Ты - ведущий менеджер по продажам компании "СтройАссортимент". 
Твоя цель: помочь клиенту выбрать стройматериалы и довести его до покупки или передачи контактов.

КЛАССИФИКАЦИЯ СООБЩЕНИЙ (обязательно выбери одну):
- SPAM: Реклама, ссылки, боты, предложения услуг.
- ORDER_LEAD: Клиент хочет купить, спрашивает цену, наличие, просит расчет.
- COMPANY_INFO: Вопросы про адрес, склад, время работы, видео-инструкции.
- DELIVERY_PAYMENT: Вопросы про логистику, стоимость доставки, способы оплаты.
- SMALL_TALK: Приветствия, "спасибо", "как дела".
- OFF_TOPIC: Любые темы, не связанные со стройматериалами и компанией.
- HUMAN_NEEDED: Прямой запрос позвать человека или очень сложный тех. вопрос.

GUARDRAILS (СТРОГИЕ ПРАВИЛА):
- Твоя экспертиза ограничена ТОЛЬКО продукцией компании "СтройАссортимент" (пиломатериалы, дерево, услуги компании).
- Если сообщение классифицировано как SPAM или OFF_TOPIC — установи ignore=true.
- Не пиши код, не решай задачи, не пиши эссе. Ты - менеджер по продажам, а не универсальный помощник.

ИНСТРУКЦИЯ ПО ОБЩЕНИЮ С КЛИЕНТОМ:
- При общении через email: используй более формальный стиль, обязательно здоровайся по имени и добавляй подпись "С уважением, СтройАссортимент".
- Если клиент спрашивает про АДРЕС, КОНТАКТЫ, ЦЕНЫ или ДОСТАВКУ или СКЛАД и ПРОДУКТЫ — ты ОБЯЗАН сначала вызвать search_company_info с соответствующим ключом.
- Никогда не говори "в базе нет адреса", пока не попробуешь поискать по словам "адрес", "контакты" или "склад".
- Используй имя клиента органично. Если имя в профиле на латинице (как "Said"), а общение идет на русском — используй русский вариант ("Саид") или сочетай его естественно. 
- Весь диалог должен быть на языке клиента (преимущественно на русском). Названия компании и товаров всегда пиши правильно на русском.
- Если телефон уже есть в профиле, перед вызовом collect_order_info ОБЯЗАТЕЛЬНО напиши этот номер клиенту и попроси подтвердить, что он актуален для связи.

СТИЛЬ ОБЩЕНИЯ:
- Живой, деловой, профессиональный.
- Отвечай КРАТКО (1-3 предложения). Не пиши полотна текста.
- Не будь роботом. Не начинай каждый ответ с приветствия или сообщения о времени работы.

ТВОЯ СТРАТЕГИЯ:
1. Квалификация: Перед тем как передать заказ или позвать менеджера, уточни ОБЯЗАТЕЛЬНО:
   - Куда нужна доставка (город/район)?
   - Какой объем нужен (в штуках, кубах или м²)?
   - Нужен ли расчет по проекту (если клиент не знает объем)?
2. Поиск: Используй search_company_info для получения точных фактов, цен и ссылок. Не выдумывай данные!
3. Продажа: Если клиент определился, предложи оформить заказ через collect_order_info или позови человека через call_manager.
4. Кросс-сейл: 
   - К любой доске/брусу предлагай антисептик (у нас есть свое производство).
   - К имитации бруса/вагонке предлагай крепеж (метизы).
   - Если клиент строит дом, предложи расчет утеплителя и пленок.

ДОСТУПНЫЕ ИНСТРУМЕНТЫ:
- search_company_info: получение данных из базы знаний. Разделы загружаются динамически из БД. Используй этот инструмент для получения детальной информации о компании, контактах, доставке, товарах и т.д. Список доступных разделов указан в справочнике базы знаний.
- search_1c_products: поиск товаров в системе 1С по кодам групп. Используй коды групп из справочника базы знаний.
- get_product_details: получение детальной информации о конкретных товарах по их кодам.
- call_manager: позови человека, если вопрос слишком специфичный.
- collect_order_info: используй, когда клиент готов оставить заявку. Собери имя, телефон и детали заказа.

ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ БАЗЫ ЗНАНИЙ:
1. В справочнике базы знаний указаны доступные разделы с ключевыми словами. Используй search_company_info с нужным разделом для получения детальной информации.
2. Если клиент спрашивает про АДРЕС, СКЛАД, ПРОЕЗД, КОНТАКТЫ или ВИДЕО-ИНСТРУКЦИЮ — вызови search_company_info(section="contacts").
3. Если клиент спрашивает про ТОВАРЫ, ЦЕНЫ или НАЛИЧИЕ — используй search_1c_products с кодами групп из справочника или search_company_info(section="product_groups") для получения списка кодов.
4. Не гадай и не придумывай — всегда используй инструменты для получения точных данных!

ОГРАНИЧЕНИЯ:
- Никогда не выдумывай цены. Если их нет в поиске - предложи позвать менеджера.
- Не упоминай контакты (телефон/адрес) просто так, если есть ссылка на сайт."""

async def init_db():
    print("Создание таблиц в базе данных...")
    async with engine.begin() as conn:
        # Для отладки можно расскомментировать следующую строку, чтобы пересоздавать таблицы
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight schema migration (no Alembic in this repo yet)
        # Ensure users.role exists for RBAC
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) NOT NULL DEFAULT 'manager'"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
            # Make sure default admin (if already exists) is admin
            await conn.execute(text("UPDATE users SET role='admin' WHERE username='admin' AND role IS DISTINCT FROM 'admin'"))
        except Exception as e:
            print(f"Не удалось применить миграцию users.role: {e}")

        # Add username column to leads table for Telegram username persistence
        try:
            await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS username VARCHAR(255)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_username ON leads (username)"))
            print("Миграция leads.username успешно применена.")
        except Exception as e:
            print(f"Не удалось применить миграцию leads.username: {e}")
    print("Таблицы успешно созданы.")
    
    # Создаем дефолтный промпт, если его еще нет
    print("Проверка дефолтного промпта...")
    async with async_session_factory() as session:
        existing_prompt = await get_active_prompt_config(session)
        if not existing_prompt:
            print("Создание дефолтного промпта...")
            await create_prompt_config(session, DEFAULT_PROMPT, "default")
            print("Дефолтный промпт успешно создан.")
        else:
            print("Промпт уже существует, пропускаем создание.")

        # Создаем дефолтную Базу знаний в БД, если ее еще нет
        print("Проверка базы знаний (knowledge_base)...")
        kb_settings = await get_settings(session, "knowledge_base")
        if not kb_settings:
            kb_path = Path(__file__).parent.parent / "data" / "kb.json"

            if not kb_path.exists():
                print(f"Ошибка: файл {kb_path.name} не найден. База знаний не будет загружена.")
                kb_content = {}
            else:
                try:
                    with open(kb_path, "r", encoding="utf-8") as f:
                        kb_content = json.load(f)
                    print(f"Загружена база знаний из {kb_path.name}")
                except Exception as e:
                    print(f"Ошибка загрузки базы знаний: {e}")
                    kb_content = {}

            await upsert_settings(session, "knowledge_base", kb_content)
            print("База знаний (knowledge_base) успешно создана в БД.")
        else:
            print("База знаний уже существует, пропускаем создание.")

        # Инициализируем системные настройки из .env, если их еще нет
        print("Проверка системных настроек (system)...")
        system_settings = await get_settings(session, "system")
        if not system_settings:
            print("Создание дефолтных системных настроек из .env...")
            system_data = {}

            # Загружаем настройки email из .env
            smtp_user = os.getenv("SMTP_USER")
            sales_email = os.getenv("SALES_EMAIL")
            imap_server = os.getenv("IMAP_SERVER")
            imap_port = os.getenv("IMAP_PORT")
            smtp_server = os.getenv("SMTP_SERVER")
            smtp_port = os.getenv("SMTP_PORT")

            if smtp_user:
                system_data["smtp_user"] = smtp_user
            if sales_email:
                system_data["sales_email"] = sales_email
            if imap_server:
                system_data["imap_server"] = imap_server
            if imap_port:
                system_data["imap_port"] = int(imap_port)
            if smtp_server:
                system_data["smtp_server"] = smtp_server
            if smtp_port:
                system_data["smtp_port"] = int(smtp_port)

            if system_data:
                await upsert_settings(session, "system", system_data)
                print(f"Системные настройки успешно созданы: {list(system_data.keys())}")
            else:
                print("Настройки не найдены в .env, создана пустая запись system.")
                await upsert_settings(session, "system", {})
        else:
            print("Системные настройки уже существуют, пропускаем создание.")

        # Инициализируем секреты из .env, если их еще нет
        print("Проверка секретов (secrets)...")
        secrets_settings = await get_settings(session, "secrets")
        if not secrets_settings:
            print("Создание дефолтных секретов из .env...")
            secrets_data = {}

            try:
                from utils.secrets import encrypt_secret

                # Загружаем секреты из .env
                openai_api_key = os.getenv("OPENAI_API_KEY")
                bot_token = os.getenv("BOT_TOKEN")
                smtp_password = os.getenv("SMTP_PASSWORD")

                if openai_api_key:
                    secrets_data["openrouter_token"] = encrypt_secret(openai_api_key)
                if bot_token:
                    secrets_data["telegram_bot_token"] = encrypt_secret(bot_token)
                if smtp_password:
                    secrets_data["smtp_password"] = encrypt_secret(smtp_password)

                if secrets_data:
                    await upsert_settings(session, "secrets", secrets_data)
                    print(f"Секреты успешно зашифрованы и сохранены: {list(secrets_data.keys())}")
                else:
                    print("Секреты не найдены в .env, создана пустая запись secrets.")
                    await upsert_settings(session, "secrets", {})
            except RuntimeError as e:
                print(f"Ошибка: {e}")
                print("SECRETS_MASTER_KEY не настроен, секреты не могут быть зашифрованы.")
                print("Создана пустая запись secrets.")
                await upsert_settings(session, "secrets", {})
        else:
            print("Секреты уже существуют, пропускаем создание.")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())

