"""
FastAPI микросервис для обработки сообщений через AI агента.
Принимает запросы от Telegram бота и возвращает ответы агента.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from schemas.service_schemas import HealthResponse
import asyncio
import json
from pathlib import Path

# Настройка логирования
from utils.logger import setup_logging
logger = setup_logging("api")

# Импорт роутеров
from services.ai_router import router as ai_router
from services.crm_router import router as crm_router

# Создаем FastAPI приложение
app = FastAPI(
    title="AI Service",
    description="Микросервис для обработки сообщений через AI агента продаж",
    version="0.1.0"
)

# Настройка CORS (если нужно обращаться с фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Подключаем роутеры
app.include_router(ai_router)
app.include_router(crm_router)


@app.on_event("startup")
async def startup_event():
    """
    Проверяет наличие дефолтных промпта и KB в БД при старте сервиса.
    Загружает их из файлов, если они отсутствуют.
    """
    try:
        from db.session import async_session_factory
        from db.repository import get_active_prompt_config, create_prompt_config, get_settings, upsert_settings
        
        async with async_session_factory() as session:
            # Проверяем промпт
            existing_prompt = await get_active_prompt_config(session)
            if not existing_prompt:
                logger.info("Дефолтный промпт не найден в БД, загружаем...")
                # Загружаем дефолтный промпт из init_db.py
                from db.init_db import DEFAULT_PROMPT
                await create_prompt_config(session, DEFAULT_PROMPT, "default")
                await session.commit()
                logger.info("Дефолтный промпт загружен в БД")
            
            # Проверяем KB
            kb_settings = await get_settings(session, "knowledge_base")
            if not kb_settings:
                logger.info("База знаний не найдена в БД, загружаем дефолтную...")
                
                kb_path = Path(__file__).parent / "data" / "kb.json"
                
                if not kb_path.exists():
                    logger.error(f"Файл {kb_path.name} не найден. База знаний не будет загружена.")
                    kb_content = {}
                else:
                    try:
                        with open(kb_path, "r", encoding="utf-8") as f:
                            kb_content = json.load(f)
                        logger.info(f"Загружена база знаний из {kb_path.name}")
                    except Exception as e:
                        logger.error(f"Ошибка загрузки базы знаний: {e}")
                        kb_content = {}
                
                if kb_content:
                    await upsert_settings(session, "knowledge_base", kb_content)
                    await session.commit()
                    logger.info("Дефолтная база знаний загружена в БД")
            
            # Обновляем ParamsManager после загрузки дефолтных значений
            from params_manager import ParamsManager
            params_manager = ParamsManager()
            await params_manager.load_all(force=True)
            logger.info("ParamsManager обновлен после загрузки дефолтных значений")
            
    except Exception as e:
        logger.error(f"Ошибка при инициализации дефолтных значений: {e}", exc_info=True)
        # Не падаем, если не удалось загрузить - возможно БД еще не готова


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", service="ai-consultant")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5537)
