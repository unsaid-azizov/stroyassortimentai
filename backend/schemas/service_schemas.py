from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

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
    updated_context: Optional[List[dict]] = None  # Полная история сообщений с ToolMessage
    # Optional metadata for clients (Telegram/Email) to handle ignored messages differently
    ignored: bool = False
    category: Optional[str] = None
    reasoning: Optional[str] = None

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
    username: Optional[str]
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


class OrderSubmissionDetailResponse(BaseModel):
    """Детальная информация о заказе с полным payload."""
    id: str
    created_at: datetime
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    currency: str = "RUB"
    subtotal: Optional[float] = None
    total: Optional[float] = None
    items_count: Optional[int] = None
    status: str
    payload: Dict  # Полный OrderInfo со всеми деталями

    class Config:
        from_attributes = True


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
    content: str  # Plain text format


class UpdateKnowledgeBaseRequest(BaseModel):
    content: str  # Plain text format


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
