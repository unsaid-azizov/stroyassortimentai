from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Lead, Thread, Message, AIStats
from typing import Optional
import uuid

async def get_or_create_lead(
    session: AsyncSession, 
    channel: str, 
    external_id: str, 
    name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None
) -> Lead:
    """Находит лида строго по ID канала. Никакой склейки на этом этапе."""
    stmt = select(Lead).where(
        Lead.external_id == external_id, 
        Lead.channel == channel
    )
    result = await session.execute(stmt)
    lead = result.scalar_one_or_none()
    
    if not lead:
        lead = Lead(
            channel=channel, 
            external_id=external_id, 
            name=name,
            phone=phone,
            email=email
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    
    return lead

async def get_or_create_thread(session: AsyncSession, lead_id: uuid.UUID) -> Thread:
    """Находит активный тред для лида или создает новый."""
    stmt = select(Thread).where(
        Thread.lead_id == lead_id, 
        Thread.status != "CLOSED"
    ).order_by(Thread.created_at.desc())
    
    result = await session.execute(stmt)
    thread = result.scalar_one_or_none()
    
    if not thread:
        thread = Thread(lead_id=lead_id)
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
    
    return thread

async def save_message(
    session: AsyncSession,
    thread_id: uuid.UUID,
    sender_role: str,
    content: str,
    sender_id: Optional[str] = None
) -> Message:
    """Сохраняет сообщение в лог."""
    message = Message(
        thread_id=thread_id,
        sender_role=sender_role,
        sender_id=sender_id,
        content=content
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message

async def save_ai_stats(
    session: AsyncSession,
    message_id: uuid.UUID,
    category: str,
    reasoning: Optional[str] = None,
    model_name: Optional[str] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None,
    cost: Optional[float] = None,
    ignored: bool = False
) -> AIStats:
    """Сохраняет детальную аналитику ответа ИИ."""
    stats = AIStats(
        message_id=message_id,
        category=category,
        reasoning=reasoning,
        model_name=model_name,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost=cost,
        ignored=ignored
    )
    session.add(stats)
    await session.commit()
    await session.refresh(stats)
    return stats

