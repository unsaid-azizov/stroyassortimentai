"""
FastAPI микросервис для обработки сообщений через AI агента.
Принимает запросы от Telegram бота и возвращает ответы агента.
"""
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging
import asyncio
import json
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage
from agent import agent, load_company_info, dynamic_prompt_template
from db.session import async_session_factory
from db.repository import (
    get_or_create_lead, get_or_create_thread, save_message, save_ai_stats,
    get_leads, get_lead_by_id, get_threads, get_thread_by_id, get_messages,
    update_thread_status, get_stats_overview, get_stats_categories,
    get_stats_timeline, get_stats_funnel, get_stats_costs,
    get_active_prompt_config, create_prompt_config,
    get_user_by_username, get_user_by_email, create_user,
    get_business_metrics, get_channel_distribution, get_enhanced_funnel,
    get_order_leads_timeline
)
from auth import authenticate_user, create_access_token, verify_token, get_password_hash

# Настройка логирования
from utils.logger import setup_logging
logger = setup_logging("ai_service")

# Создаем FastAPI приложение
app = FastAPI(
    title="AI Consultant Service",
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


# Модели для аутентификации
class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignupResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None


# Модели для лидов
class LeadResponse(BaseModel):
    id: str
    external_id: Optional[str]
    channel: str
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    last_seen: datetime
    
    class Config:
        from_attributes = True


class LeadsListResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int
    limit: int


class ThreadResponse(BaseModel):
    id: str
    lead_id: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class MessageResponseDetail(BaseModel):
    id: str
    thread_id: str
    sender_role: str
    sender_id: Optional[str]
    content: str
    created_at: datetime
    ai_stats: Optional[Dict] = None
    
    class Config:
        from_attributes = True


class ThreadDetailResponse(BaseModel):
    id: str
    lead_id: str
    status: str
    created_at: datetime
    lead: LeadResponse
    messages: List[MessageResponseDetail]
    
    class Config:
        from_attributes = True


class UpdateThreadStatusRequest(BaseModel):
    status: str


# Модели для статистики
class StatsOverviewResponse(BaseModel):
    total_leads: int
    active_threads: int
    total_messages: int
    avg_cost: float


class CategoryStatsResponse(BaseModel):
    category: str
    count: int


class TimelineResponse(BaseModel):
    date: str
    value: float


class FunnelResponse(BaseModel):
    stage: str
    count: int


class CostsResponse(BaseModel):
    total: float
    average: float


# Модели для бизнес-метрик
class BusinessMetricsResponse(BaseModel):
    potential_orders: int
    new_leads_today: int
    new_leads_week: int
    ai_processed_messages: int
    human_needed_count: int
    spam_filtered: int
    conversion_rate: float
    ai_efficiency: float


class ChannelDistributionItem(BaseModel):
    channel: str
    leads: int
    order_leads: int


class ChannelDistributionResponse(BaseModel):
    channels: List[ChannelDistributionItem]


class EnhancedFunnelItem(BaseModel):
    stage: str
    count: int


class EnhancedFunnelResponse(BaseModel):
    funnel: List[EnhancedFunnelItem]


# Модели для настроек
class PromptConfigResponse(BaseModel):
    id: str
    name: str
    version: int
    content: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UpdatePromptRequest(BaseModel):
    content: str
    name: str = "default"


class KnowledgeBaseResponse(BaseModel):
    content: Dict


class UpdateKnowledgeBaseRequest(BaseModel):
    content: Dict


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


# ==================== CRM API ENDPOINTS ====================

# Аутентификация
@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Вход в систему."""
    user = await authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )
    access_token = create_access_token(data={"sub": user["username"], "user_id": user["id"]})
    return LoginResponse(access_token=access_token)


@app.post("/api/auth/signup", response_model=SignupResponse)
async def signup(request: SignupRequest):
    """Регистрация нового пользователя."""
    async with async_session_factory() as db_session:
        # Проверяем, что username и email уникальны
        existing_user = await get_user_by_username(db_session, request.username)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Username already exists"
            )
        
        if request.email:
            existing_email = await get_user_by_email(db_session, request.email)
            if existing_email:
                raise HTTPException(
                    status_code=400,
                    detail="Email already exists"
                )
        
        # Хешируем пароль
        hashed_password = get_password_hash(request.password)
        
        # Создаем пользователя
        try:
            user = await create_user(
                db_session,
                username=request.username,
                email=request.email,
                hashed_password=hashed_password,
                full_name=request.full_name
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Создаем токен
        access_token = create_access_token(data={"sub": user.username, "user_id": str(user.id)})
        
        return SignupResponse(
            access_token=access_token,
            user={
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name
            }
        )


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user(current_user: dict = Depends(verify_token)):
    """Получить текущего пользователя."""
    async with async_session_factory() as db_session:
        user = await get_user_by_username(db_session, current_user["username"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(
            username=user.username,
            email=user.email,
            full_name=user.full_name
        )


# Лиды и переписки
@app.get("/api/leads", response_model=LeadsListResponse)
async def list_leads(
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    has_phone: Optional[bool] = Query(None),
    has_email: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(verify_token)
):
    """Получить список лидов с фильтрами."""
    async with async_session_factory() as db_session:
        leads, total = await get_leads(
            db_session,
            channel=channel,
            status=status,
            date_from=date_from,
            date_to=date_to,
            category=category,
            search=search,
            has_phone=has_phone,
            has_email=has_email,
            page=page,
            limit=limit
        )
        return LeadsListResponse(
            leads=[LeadResponse.model_validate(lead) for lead in leads],
            total=total,
            page=page,
            limit=limit
        )


@app.get("/api/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    current_user: dict = Depends(verify_token)
):
    """Получить детали лида."""
    async with async_session_factory() as db_session:
        lead = await get_lead_by_id(db_session, uuid.UUID(lead_id))
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return LeadResponse.model_validate(lead)


@app.get("/api/threads", response_model=List[ThreadResponse])
async def list_threads(
    lead_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(verify_token)
):
    """Получить список тредов."""
    async with async_session_factory() as db_session:
        thread_lead_id = uuid.UUID(lead_id) if lead_id else None
        threads = await get_threads(db_session, lead_id=thread_lead_id, status=status)
        return [ThreadResponse.model_validate(thread) for thread in threads]


@app.get("/api/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    thread_id: str,
    current_user: dict = Depends(verify_token)
):
    """Получить детали треда с сообщениями."""
    async with async_session_factory() as db_session:
        thread = await get_thread_by_id(db_session, uuid.UUID(thread_id))
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        
        messages = await get_messages(db_session, uuid.UUID(thread_id))
        messages_data = []
        for msg in messages:
            msg_dict = MessageResponseDetail.model_validate(msg).model_dump()
            if msg.ai_stats:
                msg_dict["ai_stats"] = {
                    "category": msg.ai_stats.category,
                    "reasoning": msg.ai_stats.reasoning,
                    "tokens_input": msg.ai_stats.tokens_input,
                    "tokens_output": msg.ai_stats.tokens_output,
                    "cost": msg.ai_stats.cost,
                    "ignored": msg.ai_stats.ignored
                }
            messages_data.append(MessageResponseDetail(**msg_dict))
        
        return ThreadDetailResponse(
            id=str(thread.id),
            lead_id=str(thread.lead_id),
            status=thread.status,
            created_at=thread.created_at,
            lead=LeadResponse.model_validate(thread.lead),
            messages=messages_data
        )


@app.get("/api/threads/{thread_id}/messages", response_model=List[MessageResponseDetail])
async def get_thread_messages(
    thread_id: str,
    current_user: dict = Depends(verify_token)
):
    """Получить сообщения треда."""
    async with async_session_factory() as db_session:
        messages = await get_messages(db_session, uuid.UUID(thread_id))
        messages_data = []
        for msg in messages:
            msg_dict = MessageResponseDetail.model_validate(msg).model_dump()
            if msg.ai_stats:
                msg_dict["ai_stats"] = {
                    "category": msg.ai_stats.category,
                    "reasoning": msg.ai_stats.reasoning,
                    "tokens_input": msg.ai_stats.tokens_input,
                    "tokens_output": msg.ai_stats.tokens_output,
                    "cost": msg.ai_stats.cost,
                    "ignored": msg.ai_stats.ignored
                }
            messages_data.append(MessageResponseDetail(**msg_dict))
        return messages_data


@app.patch("/api/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    request: UpdateThreadStatusRequest,
    current_user: dict = Depends(verify_token)
):
    """Обновить статус треда."""
    async with async_session_factory() as db_session:
        thread = await update_thread_status(db_session, uuid.UUID(thread_id), request.status)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        return ThreadResponse.model_validate(thread)


# Статистика
@app.get("/api/stats/overview", response_model=StatsOverviewResponse)
async def get_stats_overview_endpoint(
    current_user: dict = Depends(verify_token)
):
    """Получить общую статистику."""
    async with async_session_factory() as db_session:
        stats = await get_stats_overview(db_session)
        return StatsOverviewResponse(**stats)


@app.get("/api/stats/categories", response_model=List[CategoryStatsResponse])
async def get_stats_categories_endpoint(
    current_user: dict = Depends(verify_token)
):
    """Получить распределение по категориям."""
    async with async_session_factory() as db_session:
        categories = await get_stats_categories(db_session)
        return [CategoryStatsResponse(**cat) for cat in categories]


@app.get("/api/stats/timeline", response_model=List[TimelineResponse])
async def get_stats_timeline_endpoint(
    metric: str = Query(..., description="leads, messages, or costs"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: dict = Depends(verify_token)
):
    """Получить динамику по дням."""
    async with async_session_factory() as db_session:
        timeline = await get_stats_timeline(db_session, metric, date_from, date_to)
        return [TimelineResponse(**item) for item in timeline]


@app.get("/api/stats/funnel", response_model=List[FunnelResponse])
async def get_stats_funnel_endpoint(
    current_user: dict = Depends(verify_token)
):
    """Получить воронку конверсий."""
    async with async_session_factory() as db_session:
        funnel = await get_stats_funnel(db_session)
        return [FunnelResponse(**item) for item in funnel]


@app.get("/api/stats/costs", response_model=CostsResponse)
async def get_stats_costs_endpoint(
    current_user: dict = Depends(verify_token)
):
    """Получить статистику по стоимости API."""
    async with async_session_factory() as db_session:
        costs = await get_stats_costs(db_session)
        return CostsResponse(**costs)


@app.get("/api/stats/business", response_model=BusinessMetricsResponse)
async def get_business_metrics_endpoint(
    current_user: dict = Depends(verify_token)
):
    """Получить бизнес-метрики для демонстрации ценности системы."""
    async with async_session_factory() as db_session:
        metrics = await get_business_metrics(db_session)
        return BusinessMetricsResponse(**metrics)


@app.get("/api/stats/channels", response_model=ChannelDistributionResponse)
async def get_channel_distribution_endpoint(
    current_user: dict = Depends(verify_token)
):
    """Получить распределение лидов и ORDER_LEAD по каналам."""
    async with async_session_factory() as db_session:
        channels = await get_channel_distribution(db_session)
        return ChannelDistributionResponse(channels=channels)


@app.get("/api/stats/funnel-enhanced", response_model=EnhancedFunnelResponse)
async def get_enhanced_funnel_endpoint(
    current_user: dict = Depends(verify_token)
):
    """Получить расширенную воронку продаж."""
    async with async_session_factory() as db_session:
        funnel = await get_enhanced_funnel(db_session)
        return EnhancedFunnelResponse(funnel=funnel)


@app.get("/api/stats/order-leads-timeline", response_model=List[TimelineResponse])
async def get_order_leads_timeline_endpoint(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: dict = Depends(verify_token)
):
    """Получить динамику потенциальных заказов (ORDER_LEAD) по дням."""
    async with async_session_factory() as db_session:
        timeline = await get_order_leads_timeline(db_session, date_from, date_to)
        return [TimelineResponse(**item) for item in timeline]


# Настройки агента
@app.get("/api/settings/prompt", response_model=PromptConfigResponse)
async def get_prompt(
    current_user: dict = Depends(verify_token)
):
    """Получить текущий промпт."""
    async with async_session_factory() as db_session:
        config = await get_active_prompt_config(db_session)
        if not config:
            # Возвращаем дефолтный промпт из agent.py
            # Для этого нужно извлечь системный промпт из функции
            # Пока возвращаем пустой контент, который фронтенд может заполнить
            raise HTTPException(status_code=404, detail="No active prompt config found")
        return PromptConfigResponse.model_validate(config)


@app.put("/api/settings/prompt", response_model=PromptConfigResponse)
async def update_prompt(
    request: UpdatePromptRequest,
    current_user: dict = Depends(verify_token)
):
    """Обновить промпт (hot reload)."""
    async with async_session_factory() as db_session:
        config = await create_prompt_config(db_session, request.content, request.name)
        # TODO: Hot reload агента - нужно перезагрузить промпт в памяти
        # Это будет реализовано через глобальную переменную или singleton
        return PromptConfigResponse.model_validate(config)


@app.get("/api/settings/knowledge-base", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    current_user: dict = Depends(verify_token)
):
    """Получить базу знаний."""
    kb_data = load_company_info()
    return KnowledgeBaseResponse(content=kb_data)


@app.put("/api/settings/knowledge-base", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    request: UpdateKnowledgeBaseRequest,
    current_user: dict = Depends(verify_token)
):
    """Обновить базу знаний (hot reload)."""
    # Сохраняем в файл
    kb_path = Path(__file__).parent / "data" / "company_info.json"
    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump(request.content, f, ensure_ascii=False, indent=2)
    
    # TODO: Hot reload - перезагрузить в памяти агента
    return KnowledgeBaseResponse(content=request.content)


@app.post("/api/settings/reload-agent")
async def reload_agent(
    current_user: dict = Depends(verify_token)
):
    """Принудительная перезагрузка агента."""
    # TODO: Реализовать перезагрузку промпта и БЗ в памяти
    return {"status": "ok", "message": "Agent reloaded"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5537)

