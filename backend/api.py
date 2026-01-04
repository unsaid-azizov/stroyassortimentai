"""
FastAPI микросервис для обработки сообщений через AI агента.
Принимает запросы от Telegram бота и возвращает ответы агента.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from schemas.service_schemas import HealthResponse

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

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", service="ai-consultant")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5537)
