"""
FastAPI микросервис для обработки сообщений через AI агента.
Принимает запросы от Telegram бота и возвращает ответы агента.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
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
from params_manager import ParamsManager
from runtime_config import refresh_runtime_config

# Создаем глобальный инстанс ParamsManager (singleton)
params_manager = ParamsManager()

# Импорт для обработки ошибки превышения лимита токенов
try:
    from openai import LengthFinishReasonError
except ImportError:
    # Если прямой импорт не работает, используем общий Exception
    LengthFinishReasonError = type('LengthFinishReasonError', (Exception,), {})
from db.session import async_session_factory
from db.repository import (
    get_leads, 
    get_lead_by_id, 
    get_threads, 
    get_thread_by_id, 
    get_messages,
    update_thread_status, 
    get_stats_overview, 
    get_stats_categories,
    get_stats_timeline, 
    get_stats_funnel, 
    get_stats_costs,
    get_active_prompt_config, 
    create_prompt_config,
    get_user_by_username, 
    get_business_metrics, 
    get_channel_distribution, 
    get_enhanced_funnel,
    get_order_leads_timeline, 
    get_settings, 
    upsert_settings,
    get_order_submissions,
    update_user_password,
)
from auth import authenticate_user, create_access_token, verify_token, get_password_hash, get_current_user, require_roles, verify_password
from schemas.service_schemas import (
    HealthResponse,
    LoginRequest,
    SignupRequest,
    UserResponse,
    ChangePasswordRequest,
    LeadsListResponse,
    LeadResponse,
    OrdersListResponse,
    OrderSubmissionDetailResponse,
    ThreadResponse,
    ThreadDetailResponse,
    MessageResponseDetail,
    UpdateThreadStatusRequest,
    StatsOverviewResponse,
    CategoryStatsResponse,
    TimelineResponse,
    FunnelResponse,
    CostsResponse,
    BusinessMetricsResponse,
    ChannelDistributionResponse,
    EnhancedFunnelResponse,
    PromptConfigResponse,
    UpdatePromptRequest,
    KnowledgeBaseResponse,
    UpdateKnowledgeBaseRequest,
    SettingsResponse,
    SettingsUpdateRequest,
    SecretsUpdateRequest,
    LoginResponse,
    SignupResponse,
    SettingsPublic, 
    SecretStatus,
    OrderSubmissionResponse, 
)
from utils.secrets import encrypt_secret, decrypt_secret

# Настройка логирования
from utils.logger import setup_logging
logger = setup_logging("api")

# Создаем роутер для CRM эндпоинтов
router = APIRouter()

# Аутентификация
@router.post("/api/auth/login", response_model=LoginResponse)
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


@router.post("/api/auth/signup", response_model=SignupResponse)
async def signup(request: SignupRequest):
    """Регистрация нового пользователя (disabled)."""
    raise HTTPException(status_code=403, detail="Signup is disabled")


@router.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Получить текущего пользователя."""
    return UserResponse(**current_user)


@router.put("/api/auth/change-password")
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
@router.get("/api/leads", response_model=LeadsListResponse)
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
                "username": lead.username,
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


@router.get("/api/leads/{lead_id}", response_model=LeadResponse)
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
            username=lead.username,
            name=lead.name,
            phone=lead.phone,
            email=lead.email,
            last_seen=lead.last_seen
        )


# Заказы (сформированные ботом)
@router.get("/api/orders", response_model=OrdersListResponse)
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


@router.get("/api/orders/{order_id}", response_model=OrderSubmissionDetailResponse)
async def get_order(
    order_id: str,
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    """Получить детали заказа."""
    async with async_session_factory() as db_session:
        from db.repository import get_order_submission_by_id

        order = await get_order_submission_by_id(db_session, uuid.UUID(order_id))
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        return OrderSubmissionDetailResponse(
            id=str(order.id),
            created_at=order.created_at,
            client_name=order.client_name,
            client_contact=order.client_contact,
            currency=order.currency,
            subtotal=order.subtotal,
            total=order.total,
            items_count=order.items_count,
            status=order.status,
            payload=order.payload or {}
        )


@router.get("/api/threads", response_model=List[ThreadResponse])
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


@router.get("/api/threads/{thread_id}", response_model=ThreadDetailResponse)
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
                username=thread.lead.username,
                name=thread.lead.name,
                phone=thread.lead.phone,
                email=thread.lead.email,
                last_seen=thread.lead.last_seen
            ),
            messages=messages_data
        )


@router.get("/api/threads/{thread_id}/messages", response_model=List[MessageResponseDetail])
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


@router.patch("/api/threads/{thread_id}", response_model=ThreadResponse)
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
@router.get("/api/stats/overview", response_model=StatsOverviewResponse)
async def get_stats_overview_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить общую статистику."""
    async with async_session_factory() as db_session:
        stats = await get_stats_overview(db_session)
        return StatsOverviewResponse(**stats)


@router.get("/api/stats/categories", response_model=List[CategoryStatsResponse])
async def get_stats_categories_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить распределение по категориям."""
    async with async_session_factory() as db_session:
        categories = await get_stats_categories(db_session)
        return [CategoryStatsResponse(**cat) for cat in categories]


@router.get("/api/stats/timeline", response_model=List[TimelineResponse])
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


@router.get("/api/stats/funnel", response_model=List[FunnelResponse])
async def get_stats_funnel_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить воронку конверсий."""
    async with async_session_factory() as db_session:
        funnel = await get_stats_funnel(db_session)
        return [FunnelResponse(**item) for item in funnel]


@router.get("/api/stats/costs", response_model=CostsResponse)
async def get_stats_costs_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить статистику по стоимости API."""
    async with async_session_factory() as db_session:
        costs = await get_stats_costs(db_session)
        return CostsResponse(**costs)


@router.get("/api/stats/business", response_model=BusinessMetricsResponse)
async def get_business_metrics_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить бизнес-метрики для демонстрации ценности системы."""
    async with async_session_factory() as db_session:
        metrics = await get_business_metrics(db_session)
        return BusinessMetricsResponse(**metrics)


@router.get("/api/stats/channels", response_model=ChannelDistributionResponse)
async def get_channel_distribution_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить распределение лидов и ORDER_LEAD по каналам."""
    async with async_session_factory() as db_session:
        channels = await get_channel_distribution(db_session)
        return ChannelDistributionResponse(channels=channels)


@router.get("/api/stats/funnel-enhanced", response_model=EnhancedFunnelResponse)
async def get_enhanced_funnel_endpoint(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить расширенную воронку продаж."""
    async with async_session_factory() as db_session:
        funnel = await get_enhanced_funnel(db_session)
        return EnhancedFunnelResponse(funnel=funnel)


@router.get("/api/stats/order-leads-timeline", response_model=List[TimelineResponse])
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
@router.get("/api/settings/prompt", response_model=PromptConfigResponse)
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


@router.put("/api/settings/prompt", response_model=PromptConfigResponse)
async def update_prompt(
    request: UpdatePromptRequest,
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Обновить промпт (hot reload)."""
    async with async_session_factory() as db_session:
        config = await create_prompt_config(db_session, request.content, request.name)
        # Force refresh ParamsManager immediately
        await params_manager.load_prompt(force=True)
        return PromptConfigResponse(
            id=str(config.id),
            name=config.name,
            version=config.version,
            content=config.content,
            is_active=config.is_active,
            created_at=config.created_at
        )


@router.get("/api/settings/knowledge-base", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Получить базу знаний (в текстовом формате)."""
    async with async_session_factory() as db_session:
        kb_settings = await get_settings(db_session, "knowledge_base")
        kb_data = kb_settings.value if kb_settings and kb_settings.value else ""

        # Если KB еще в старом JSON формате, конвертируем в текст
        if isinstance(kb_data, dict):
            from utils.kb_parser import kb_dict_to_text
            kb_data = kb_dict_to_text(kb_data)

        # Убеждаемся, что это строка
        if not isinstance(kb_data, str):
            kb_data = ""

    return KnowledgeBaseResponse(content=kb_data)


@router.put("/api/settings/knowledge-base", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    request: UpdateKnowledgeBaseRequest,
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Обновить базу знаний (hot reload)."""
    async with async_session_factory() as db_session:
        await upsert_settings(db_session, "knowledge_base", request.content)
    # Force refresh ParamsManager immediately
    await params_manager.load_knowledge_base(force=True)
    return KnowledgeBaseResponse(content=request.content)


@router.get("/api/settings", response_model=SettingsResponse)
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


@router.put("/api/settings", response_model=SettingsResponse)
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


@router.put("/api/settings/secrets", response_model=SettingsResponse)
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


@router.post("/api/catalog/sync")
async def trigger_catalog_sync(current_user: dict = Depends(require_roles("admin"))):
    """
    Запустить синхронизацию каталога из 1C вручную.
    Доступно только администраторам.
    """
    from services.catalog_sync import catalog_sync_service

    logger.info(f"Manual catalog sync triggered by user: {current_user.get('username')}")

    # Запускаем синхронизацию в фоне
    asyncio.create_task(catalog_sync_service.sync_catalog())

    return {
        "status": "started",
        "message": "Catalog sync started in background"
    }


@router.get("/api/catalog/sync/status")
async def get_catalog_sync_status(current_user: dict = Depends(require_roles("admin", "manager"))):
    """
    Получить статус синхронизации каталога.
    """
    from services.catalog_sync import catalog_sync_service

    status = await catalog_sync_service.get_sync_status()
    return status


# Роутер экспортируется для подключения к основному приложению

