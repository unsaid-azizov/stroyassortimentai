import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, Integer, Float, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    pass

class Lead(Base):
    __tablename__ = "leads"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)  # ID в ТГ/Авито
    channel: Mapped[str] = mapped_column(String(50))  # telegram/email/avito
    name: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    threads: Mapped[List["Thread"]] = relationship(back_populates="lead", cascade="all, delete-orphan")

class Thread(Base):
    __tablename__ = "threads"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    status: Mapped[str] = mapped_column(String(50), default="AI_ONLY")  # AI_ONLY / HUMAN_INTERVENTION / CLOSED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    lead: Mapped["Lead"] = relationship(back_populates="threads")
    messages: Mapped[List["Message"]] = relationship(back_populates="thread", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id"))
    sender_role: Mapped[str] = mapped_column(String(20))  # USER / AI / MANAGER
    sender_id: Mapped[Optional[str]] = mapped_column(String(255))  # ID менеджера или NULL
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    thread: Mapped["Thread"] = relationship(back_populates="messages")
    ai_stats: Mapped[Optional["AIStats"]] = relationship(back_populates="message", uselist=False)

class AIStats(Base):
    __tablename__ = "ai_stats"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id"), unique=True)
    category: Mapped[str] = mapped_column(String(50))  # ORDER_LEAD, SPAM, и т.д.
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    model_name: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_input: Mapped[Optional[int]] = mapped_column(Integer)
    tokens_output: Mapped[Optional[int]] = mapped_column(Integer)
    cost: Mapped[Optional[float]] = mapped_column(Float)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    
    message: Mapped["Message"] = relationship(back_populates="ai_stats")

class PromptConfig(Base):
    __tablename__ = "prompt_configs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), default="default")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(32), default="manager", index=True)  # admin | manager
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Settings(Base):
    __tablename__ = "settings"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # "system" для системных настроек
    value: Mapped[dict] = mapped_column(JSON)  # JSON объект со всеми настройками
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderSubmission(Base):
    """
    Orders that were formed by the bot tools (collect_order_info / call_manager).
    We keep the payload as JSON for flexibility, plus denormalized totals for fast dashboards.
    """

    __tablename__ = "order_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Who
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    client_contact: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # Totals (denormalized)
    currency: Mapped[str] = mapped_column(String(16), default="RUB")
    subtotal: Mapped[Optional[float]] = mapped_column(Float)
    total: Mapped[Optional[float]] = mapped_column(Float)
    items_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Status
    status: Mapped[str] = mapped_column(String(32), default="SENT")  # SENT / FAILED / DRAFT
    error: Mapped[Optional[str]] = mapped_column(Text)

    # Full structured payload
    payload: Mapped[Optional[dict]] = mapped_column(JSON)



