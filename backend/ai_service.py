"""
FastAPI микросервис для обработки сообщений через AI агента.
Принимает запросы от Telegram бота и возвращает ответы агента.
"""
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging
import asyncio
import json
from typing import Any
from pydantic import ValidationError
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage
import agent as agent_module
from agent import refresh_agent_runtime_config
from runtime_config import refresh_runtime_config

# Импорт для обработки ошибки превышения лимита токенов
try:
    from openai import LengthFinishReasonError
except ImportError:
    # Если прямой импорт не работает, используем общий Exception
    LengthFinishReasonError = type('LengthFinishReasonError', (Exception,), {})
from db.session import async_session_factory
from db.repository import (
    get_or_create_lead, get_or_create_thread, save_message, save_ai_stats,
    get_leads, get_lead_by_id, get_threads, get_thread_by_id, get_messages,
    update_thread_status, get_stats_overview, get_stats_categories,
    get_stats_timeline, get_stats_funnel, get_stats_costs,
    get_active_prompt_config, create_prompt_config,
    get_user_by_username, get_user_by_email, create_user,
    get_business_metrics, get_channel_distribution, get_enhanced_funnel,
    get_order_leads_timeline, get_settings, upsert_settings, get_order_submissions,
    update_user_password,
)
from auth import authenticate_user, create_access_token, verify_token, get_password_hash, get_current_user, require_roles, verify_password

# Настройка логирования
from utils.logger import setup_logging
logger = setup_logging("ai_service")
from utils.secrets import encrypt_secret, decrypt_secret

# Создаем FastAPI приложение
app = FastAPI(
    title="AI Consultant Service",
    description="Микросервис для обработки сообщений через AI агента продаж",
    version="0.1.0"
)


@app.on_event("startup")
async def _startup_refresh_agent_runtime():
    # Load prompt + knowledge base from DB into agent runtime cache
    await refresh_runtime_config(force=True)
    await refresh_agent_runtime_config(force=True)

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
    # Optional metadata for clients (Telegram/Email) to handle ignored messages differently
    ignored: bool = False
    category: Optional[str] = None
    reasoning: Optional[str] = None


def _safe_message_preview(content: Any) -> str:
    """For logging only: avoid type errors if content is not a string."""
    try:
        if isinstance(content, str):
            return content[:120]
        return str(content)[:120]
    except Exception:
        return "<unprintable>"


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
    role: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


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


# Модели для заказов (заказы, сформированные ботом)
class OrderSubmissionResponse(BaseModel):
    id: str
    created_at: datetime
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    currency: str = "RUB"
    subtotal: Optional[float] = None
    total: Optional[float] = None
    items_count: Optional[int] = None
    status: str

    class Config:
        from_attributes = True


class OrdersListResponse(BaseModel):
    orders: List[OrderSubmissionResponse]
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
    total_leads: int
    leads_with_orders: int
    orders_count: int = 0
    orders_total_amount: float = 0.0
    orders_total_amount_week: float = 0.0


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


class SecretStatus(BaseModel):
    is_set: bool = False


class SettingsPublic(BaseModel):
    # secrets are never returned as plaintext
    openrouter_token: SecretStatus = Field(default_factory=SecretStatus)
    telegram_bot_token: SecretStatus = Field(default_factory=SecretStatus)
    smtp_user: Optional[str] = None
    smtp_password: SecretStatus = Field(default_factory=SecretStatus)
    sales_email: Optional[str] = None
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None


class SettingsResponse(BaseModel):
    settings: SettingsPublic


class SettingsUpdateRequest(BaseModel):
    # non-secret fields only
    smtp_user: Optional[str] = None
    sales_email: Optional[str] = None
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None


class SecretsUpdateRequest(BaseModel):
    openrouter_token: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    smtp_password: Optional[str] = None


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
            # Ограничиваем контекст последними 10 сообщениями, чтобы старое поведение не "залипало"
            # и новые правила промпта работали эффективнее
            context_to_use = request.context[-10:]
            for msg in context_to_use:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))
        
        messages.append(HumanMessage(content=request.message))
        
        async def _run(agent_obj):
            return await agent_obj.ainvoke({
                "messages": messages,
                "user_info": request.metadata or {}
            })

        # Strictly structured, with retries (no "parse JSON from text" fallback)
        attempts = [
            ("main", agent_module.agent),
            ("retry_temp", None),  # built lazily
            ("backup", agent_module.agent_backup),
        ]

        last_err: Optional[Exception] = None
        result_state = None
        for name, agent_obj in attempts:
            try:
                if name == "retry_temp":
                    agent_obj = agent_module.build_retry_agent(temperature=0.2)
                result_state = await asyncio.wait_for(_run(agent_obj), timeout=50.0)
                last_err = None
                break
            except asyncio.TimeoutError as e:
                last_err = e
                logger.warning(f"/chat timed out on attempt={name}")
            except (ValueError, ValidationError) as e:
                last_err = e
                logger.warning(f"Structured output failed on attempt={name}: {e}")
            except Exception as e:
                last_err = e
                logger.error(f"Unexpected error on attempt={name}: {e}", exc_info=True)

        if result_state is None:
            return MessageResponse(
                response="Извините, сервис временно перегружен. Попробуйте ещё раз через минуту.",
                user_id=request.user_id,
                chat_id=request.chat_id,
                ignored=False,
                category="TEMP_UNAVAILABLE",
                reasoning=str(last_err) if last_err else "unknown",
            )
        
        # Фоновое логирование в БД (не блокирует ответ клиенту)
        asyncio.create_task(log_interaction(request, result_state))
        
        # Извлечение ответа для клиента
        structured_data = result_state.get("structured_response")
        agent_response = ""
        should_ignore = False
        category = None
        reasoning = None

        if structured_data:
            agent_response = getattr(structured_data, "response", "")
            should_ignore = getattr(structured_data, "ignore", False)
            category = getattr(structured_data, "category", None)
            reasoning = getattr(structured_data, "reasoning", None)
        else:
            # If we got here, provider returned something unexpected even after retries.
            # Do NOT attempt to parse text. Return a generic response.
            agent_response = "Извините, я не смог сформировать корректный ответ. Попробуйте переформулировать запрос."
            should_ignore = False
        
        agent_response = agent_response.replace("—", "-")
        
        if should_ignore:
            return MessageResponse(
                response="",
                user_id=request.user_id,
                chat_id=request.chat_id,
                ignored=True,
                category=category,
                reasoning=reasoning,
            )
        
        return MessageResponse(
            response=agent_response,
            user_id=request.user_id,
            chat_id=request.chat_id,
            ignored=False,
            category=category,
            reasoning=reasoning,
        )
    
    except Exception as e:
        # Проверяем, является ли это ошибкой превышения лимита токенов
        error_str = str(e)
        error_type = type(e).__name__
        
        if "LengthFinishReasonError" in error_type or "length limit was reached" in error_str:
            # Обработка ошибки превышения лимита токенов
            logger.warning(f"Response length limit reached for user {request.user_id}: {error_str}")
            return MessageResponse(
                response="Извините, ответ получился слишком длинным. Пожалуйста, уточните ваш вопрос или запросите информацию по конкретным товарам отдельно.",
                user_id=request.user_id,
                chat_id=request.chat_id
            )
        
        # Обработка всех остальных ошибок
        logger.error(f"Error processing message: {error_str}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
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
    access_token = create_access_token(data={"sub": user["username"], "user_id": user["id"], "role": user.get("role")})
    return LoginResponse(access_token=access_token)


@app.post("/api/auth/signup", response_model=SignupResponse)
async def signup(request: SignupRequest):
    """Регистрация нового пользователя (disabled)."""
    raise HTTPException(status_code=403, detail="Signup is disabled")


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Получить текущего пользователя."""
    return UserResponse(**current_user)


@app.put("/api/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(require_roles("admin")),
):
    """Смена пароля для текущего admin пользователя."""
    new_password = (request.new_password or "").strip()
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    async with async_session_factory() as db_session:
        user = await get_user_by_username(db_session, current_user["username"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(request.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        hashed = get_password_hash(new_password)
        await update_user_password(db_session, user.id, hashed)

    return {"status": "ok"}


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
    current_user: dict = Depends(require_roles("admin", "manager"))
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
        # Конвертируем лиды в формат ответа, преобразуя UUID в строки
        leads_data = []
        for lead in leads:
            lead_dict = {
                "id": str(lead.id),
                "external_id": lead.external_id,
                "channel": lead.channel,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "last_seen": lead.last_seen
            }
            leads_data.append(LeadResponse(**lead_dict))
        
        return LeadsListResponse(
            leads=leads_data,
            total=total,
            page=page,
            limit=limit
        )


@app.get("/api/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить детали лида."""
    async with async_session_factory() as db_session:
        lead = await get_lead_by_id(db_session, uuid.UUID(lead_id))
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return LeadResponse(
            id=str(lead.id),
            external_id=lead.external_id,
            channel=lead.channel,
            name=lead.name,
            phone=lead.phone,
            email=lead.email,
            last_seen=lead.last_seen
        )


# Заказы (сформированные ботом)
@app.get("/api/orders", response_model=OrdersListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    async with async_session_factory() as db_session:
        res = await get_order_submissions(db_session, page=page, limit=limit)
        orders = res["orders"]
        total = res["total"]

        orders_data: List[OrderSubmissionResponse] = []
        for o in orders:
            orders_data.append(
                OrderSubmissionResponse(
                    id=str(o.id),
                    created_at=o.created_at,
                    client_name=o.client_name,
                    client_contact=o.client_contact,
                    currency=o.currency,
                    subtotal=o.subtotal,
                    total=o.total,
                    items_count=o.items_count,
                    status=o.status,
                )
            )

        return OrdersListResponse(orders=orders_data, total=total, page=res["page"], limit=res["limit"])


@app.get("/api/threads", response_model=List[ThreadResponse])
async def list_threads(
    lead_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить список тредов."""
    async with async_session_factory() as db_session:
        thread_lead_id = uuid.UUID(lead_id) if lead_id else None
        threads = await get_threads(db_session, lead_id=thread_lead_id, status=status)
        return [
            ThreadResponse(
                id=str(thread.id),
                lead_id=str(thread.lead_id),
                status=thread.status,
                created_at=thread.created_at
            )
            for thread in threads
        ]


@app.get("/api/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    thread_id: str,
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить детали треда с сообщениями."""
    async with async_session_factory() as db_session:
        thread = await get_thread_by_id(db_session, uuid.UUID(thread_id))
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        
        messages = await get_messages(db_session, uuid.UUID(thread_id))
        messages_data = []
        for msg in messages:
            msg_dict = {
                "id": str(msg.id),
                "thread_id": str(msg.thread_id),
                "sender_role": msg.sender_role,
                "sender_id": msg.sender_id,
                "content": msg.content,
                "created_at": msg.created_at,
                "ai_stats": None
            }
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
            lead=LeadResponse(
                id=str(thread.lead.id),
                external_id=thread.lead.external_id,
                channel=thread.lead.channel,
                name=thread.lead.name,
                phone=thread.lead.phone,
                email=thread.lead.email,
                last_seen=thread.lead.last_seen
            ),
            messages=messages_data
        )


@app.get("/api/threads/{thread_id}/messages", response_model=List[MessageResponseDetail])
async def get_thread_messages(
    thread_id: str,
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить сообщения треда."""
    async with async_session_factory() as db_session:
        messages = await get_messages(db_session, uuid.UUID(thread_id))
        messages_data = []
        for msg in messages:
            msg_dict = {
                "id": str(msg.id),
                "thread_id": str(msg.thread_id),
                "sender_role": msg.sender_role,
                "sender_id": msg.sender_id,
                "content": msg.content,
                "created_at": msg.created_at,
                "ai_stats": None
            }
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
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Обновить статус треда."""
    async with async_session_factory() as db_session:
        thread = await update_thread_status(db_session, uuid.UUID(thread_id), request.status)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        return ThreadResponse(
            id=str(thread.id),
            lead_id=str(thread.lead_id),
            status=thread.status,
            created_at=thread.created_at
        )


# Статистика
@app.get("/api/stats/overview", response_model=StatsOverviewResponse)
async def get_stats_overview_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить общую статистику."""
    async with async_session_factory() as db_session:
        stats = await get_stats_overview(db_session)
        return StatsOverviewResponse(**stats)


@app.get("/api/stats/categories", response_model=List[CategoryStatsResponse])
async def get_stats_categories_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
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
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить динамику по дням."""
    async with async_session_factory() as db_session:
        timeline = await get_stats_timeline(db_session, metric, date_from, date_to)
        return [TimelineResponse(**item) for item in timeline]


@app.get("/api/stats/funnel", response_model=List[FunnelResponse])
async def get_stats_funnel_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить воронку конверсий."""
    async with async_session_factory() as db_session:
        funnel = await get_stats_funnel(db_session)
        return [FunnelResponse(**item) for item in funnel]


@app.get("/api/stats/costs", response_model=CostsResponse)
async def get_stats_costs_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить статистику по стоимости API."""
    async with async_session_factory() as db_session:
        costs = await get_stats_costs(db_session)
        return CostsResponse(**costs)


@app.get("/api/stats/business", response_model=BusinessMetricsResponse)
async def get_business_metrics_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить бизнес-метрики для демонстрации ценности системы."""
    async with async_session_factory() as db_session:
        metrics = await get_business_metrics(db_session)
        return BusinessMetricsResponse(**metrics)


@app.get("/api/stats/channels", response_model=ChannelDistributionResponse)
async def get_channel_distribution_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить распределение лидов и ORDER_LEAD по каналам."""
    async with async_session_factory() as db_session:
        channels = await get_channel_distribution(db_session)
        return ChannelDistributionResponse(channels=channels)


@app.get("/api/stats/funnel-enhanced", response_model=EnhancedFunnelResponse)
async def get_enhanced_funnel_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить расширенную воронку продаж."""
    async with async_session_factory() as db_session:
        funnel = await get_enhanced_funnel(db_session)
        return EnhancedFunnelResponse(funnel=funnel)


@app.get("/api/stats/order-leads-timeline", response_model=List[TimelineResponse])
async def get_order_leads_timeline_endpoint(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить динамику потенциальных заказов (ORDER_LEAD) по дням."""
    async with async_session_factory() as db_session:
        timeline = await get_order_leads_timeline(db_session, date_from, date_to)
        return [TimelineResponse(**item) for item in timeline]


# Настройки агента
@app.get("/api/settings/prompt", response_model=PromptConfigResponse)
async def get_prompt(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить текущий промпт."""
    async with async_session_factory() as db_session:
        config = await get_active_prompt_config(db_session)
        if not config:
            # Возвращаем дефолтный промпт из agent.py
            # Для этого нужно извлечь системный промпт из функции
            # Пока возвращаем пустой контент, который фронтенд может заполнить
            raise HTTPException(status_code=404, detail="No active prompt config found")
        return PromptConfigResponse(
            id=str(config.id),
            name=config.name,
            version=config.version,
            content=config.content,
            is_active=config.is_active,
            created_at=config.created_at
        )


@app.put("/api/settings/prompt", response_model=PromptConfigResponse)
async def update_prompt(
    request: UpdatePromptRequest,
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Обновить промпт (hot reload)."""
    async with async_session_factory() as db_session:
        config = await create_prompt_config(db_session, request.content, request.name)
        # Hot reload агента (кеш промпта/БЗ)
        await refresh_agent_runtime_config(force=True)
        return PromptConfigResponse(
            id=str(config.id),
            name=config.name,
            version=config.version,
            content=config.content,
            is_active=config.is_active,
            created_at=config.created_at
        )


@app.get("/api/settings/knowledge-base", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить базу знаний."""
    async with async_session_factory() as db_session:
        kb_settings = await get_settings(db_session, "knowledge_base")
        kb_data = kb_settings.value if kb_settings and kb_settings.value else {}
    return KnowledgeBaseResponse(content=kb_data)


@app.put("/api/settings/knowledge-base", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    request: UpdateKnowledgeBaseRequest,
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Обновить базу знаний (hot reload)."""
    async with async_session_factory() as db_session:
        await upsert_settings(db_session, "knowledge_base", request.content)
    # Hot reload in agent runtime cache
    await refresh_agent_runtime_config()
    return KnowledgeBaseResponse(content=request.content)


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings_endpoint(
    current_user: dict = Depends(require_roles("admin"))
):
    """Получить настройки системы."""
    async with async_session_factory() as db_session:
        system_obj = await get_settings(db_session, "system")
        system_dict = system_obj.value if system_obj and system_obj.value else {}

        # Secrets: stored encrypted, never returned
        secrets_obj = await get_settings(db_session, "secrets")
        secrets_dict = secrets_obj.value if secrets_obj and secrets_obj.value else {}

        # Backward-compat: if secrets were stored in system before, migrate them once
        # Only if SECRETS_MASTER_KEY is configured (otherwise encryption can't happen)
        legacy_keys = ["openrouter_token", "telegram_bot_token", "smtp_password"]
        migrated = False
        try:
            for k in legacy_keys:
                if k in system_dict and system_dict.get(k):
                    secrets_dict[k] = encrypt_secret(str(system_dict[k]))
                    del system_dict[k]
                    migrated = True
            if migrated:
                await upsert_settings(db_session, "system", system_dict)
                await upsert_settings(db_session, "secrets", secrets_dict)
        except RuntimeError:
            # master key not configured; skip migration silently
            pass

        public = SettingsPublic(
            smtp_user=system_dict.get("smtp_user"),
            sales_email=system_dict.get("sales_email"),
            imap_server=system_dict.get("imap_server"),
            imap_port=system_dict.get("imap_port"),
            smtp_server=system_dict.get("smtp_server"),
            smtp_port=system_dict.get("smtp_port"),
            openrouter_token=SecretStatus(is_set=bool(secrets_dict.get("openrouter_token"))),
            telegram_bot_token=SecretStatus(is_set=bool(secrets_dict.get("telegram_bot_token"))),
            smtp_password=SecretStatus(is_set=bool(secrets_dict.get("smtp_password"))),
        )
        return SettingsResponse(settings=public)


@app.put("/api/settings", response_model=SettingsResponse)
async def update_settings_endpoint(
    request: SettingsUpdateRequest,
    current_user: dict = Depends(require_roles("admin"))
):
    """Обновить настройки системы."""
    async with async_session_factory() as db_session:
        existing = await get_settings(db_session, "system")
        current_settings = existing.value.copy() if existing and existing.value else {}
        
        update_dict = request.model_dump(exclude_unset=True, exclude_none=False)
        for key, value in update_dict.items():
            if value is not None and value != "":
                current_settings[key] = value
            elif key in current_settings:
                del current_settings[key]
        
        await upsert_settings(db_session, "system", current_settings)
        await refresh_runtime_config(force=True)
        logger.info(f"Settings(updated non-secrets) by user {current_user.get('username')}: {list(update_dict.keys())}")
        
        # Return merged public view
        secrets_obj = await get_settings(db_session, "secrets")
        secrets_dict = secrets_obj.value if secrets_obj and secrets_obj.value else {}
        public = SettingsPublic(
            smtp_user=current_settings.get("smtp_user"),
            sales_email=current_settings.get("sales_email"),
            imap_server=current_settings.get("imap_server"),
            imap_port=current_settings.get("imap_port"),
            smtp_server=current_settings.get("smtp_server"),
            smtp_port=current_settings.get("smtp_port"),
            openrouter_token=SecretStatus(is_set=bool(secrets_dict.get("openrouter_token"))),
            telegram_bot_token=SecretStatus(is_set=bool(secrets_dict.get("telegram_bot_token"))),
            smtp_password=SecretStatus(is_set=bool(secrets_dict.get("smtp_password"))),
        )
        return SettingsResponse(settings=public)


@app.put("/api/settings/secrets", response_model=SettingsResponse)
async def update_secrets_endpoint(
    request: SecretsUpdateRequest,
    current_user: dict = Depends(require_roles("admin")),
):
    """Обновить секреты (хранятся зашифрованно, не возвращаются в ответе)."""
    async with async_session_factory() as db_session:
        existing = await get_settings(db_session, "secrets")
        secrets_dict = existing.value.copy() if existing and existing.value else {}

        update_dict = request.model_dump(exclude_unset=True, exclude_none=False)
        updated_keys: List[str] = []
        for key, value in update_dict.items():
            if value is None or value == "":
                continue
            try:
                secrets_dict[key] = encrypt_secret(str(value))
            except RuntimeError:
                raise HTTPException(
                    status_code=400,
                    detail="SECRETS_MASTER_KEY is not configured on the server. Set it in .env and restart services.",
                )
            updated_keys.append(key)

        await upsert_settings(db_session, "secrets", secrets_dict)
        await refresh_runtime_config(force=True)
        logger.info(f"Settings(updated secrets) by user {current_user.get('username')}: {updated_keys}")

        # Return merged public view
        system_obj = await get_settings(db_session, "system")
        system_dict = system_obj.value if system_obj and system_obj.value else {}
        public = SettingsPublic(
            smtp_user=system_dict.get("smtp_user"),
            sales_email=system_dict.get("sales_email"),
            imap_server=system_dict.get("imap_server"),
            imap_port=system_dict.get("imap_port"),
            smtp_server=system_dict.get("smtp_server"),
            smtp_port=system_dict.get("smtp_port"),
            openrouter_token=SecretStatus(is_set=bool(secrets_dict.get("openrouter_token"))),
            telegram_bot_token=SecretStatus(is_set=bool(secrets_dict.get("telegram_bot_token"))),
            smtp_password=SecretStatus(is_set=bool(secrets_dict.get("smtp_password"))),
        )
        return SettingsResponse(settings=public)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5537)

