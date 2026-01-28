from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import selectinload
from db.models import Lead, Thread, Message, AIStats, PromptConfig, User, Settings, OrderSubmission
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import uuid

async def get_order_submissions(
    session: AsyncSession,
    page: int = 1,
    limit: int = 20,
) -> Dict:
    """Returns paginated bot order submissions."""
    safe_page = max(int(page or 1), 1)
    safe_limit = min(max(int(limit or 20), 1), 100)
    offset = (safe_page - 1) * safe_limit

    total_q = await session.execute(select(func.count(OrderSubmission.id)))
    total = total_q.scalar() or 0

    rows = await session.execute(
        select(OrderSubmission)
        .order_by(desc(OrderSubmission.created_at))
        .offset(offset)
        .limit(safe_limit)
    )
    orders = rows.scalars().all()
    return {"orders": orders, "total": total, "page": safe_page, "limit": safe_limit}


async def get_order_submission_by_id(
    session: AsyncSession,
    order_id: uuid.UUID
) -> Optional[OrderSubmission]:
    """Get order submission by ID."""
    result = await session.execute(
        select(OrderSubmission).where(OrderSubmission.id == order_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_lead(
    session: AsyncSession,
    channel: str,
    external_id: str,
    username: Optional[str] = None,
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
            username=username,
            name=name,
            phone=phone,
            email=email
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    else:
        # Обновляем username, name, phone, email если они пришли и изменились
        updated = False
        if username and lead.username != username:
            lead.username = username
            updated = True
        if name and lead.name != name:
            lead.name = name
            updated = True
        if phone and lead.phone != phone:
            lead.phone = phone
            updated = True
        if email and lead.email != email:
            lead.email = email
            updated = True
        if updated:
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


# Функции для CRM API

async def get_leads(
    session: AsyncSession,
    channel: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    has_phone: Optional[bool] = None,
    has_email: Optional[bool] = None,
    page: int = 1,
    limit: int = 50
) -> tuple[List[Lead], int]:
    """Получает список лидов с фильтрами и пагинацией."""
    query = select(Lead)
    
    # Фильтры
    conditions = []
    if channel:
        conditions.append(Lead.channel == channel)
    if status:
        # Статус проверяем через треды
        subquery = select(Thread.lead_id).where(Thread.status == status)
        conditions.append(Lead.id.in_(subquery))
    if date_from:
        conditions.append(Lead.last_seen >= date_from)
    if date_to:
        conditions.append(Lead.last_seen <= date_to)
    if search:
        search_pattern = f"%{search}%"
        conditions.append(
            or_(
                Lead.name.ilike(search_pattern),
                Lead.username.ilike(search_pattern),
                Lead.phone.ilike(search_pattern),
                Lead.email.ilike(search_pattern)
            )
        )
    if has_phone is not None:
        if has_phone:
            conditions.append(Lead.phone.isnot(None))
        else:
            conditions.append(Lead.phone.is_(None))
    if has_email is not None:
        if has_email:
            conditions.append(Lead.email.isnot(None))
        else:
            conditions.append(Lead.email.is_(None))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Подсчет общего количества
    count_query = select(func.count()).select_from(Lead)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Сортировка и пагинация
    query = query.order_by(desc(Lead.last_seen)).offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    leads = result.scalars().all()
    
    return list(leads), total


async def get_lead_by_id(session: AsyncSession, lead_id: uuid.UUID) -> Optional[Lead]:
    """Получает лида по ID."""
    stmt = select(Lead).where(Lead.id == lead_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_threads(
    session: AsyncSession,
    lead_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None
) -> List[Thread]:
    """Получает список тредов."""
    query = select(Thread).options(selectinload(Thread.lead))
    
    conditions = []
    if lead_id:
        conditions.append(Thread.lead_id == lead_id)
    if status:
        conditions.append(Thread.status == status)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(desc(Thread.created_at))
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_thread_by_id(session: AsyncSession, thread_id: uuid.UUID) -> Optional[Thread]:
    """Получает тред по ID."""
    stmt = select(Thread).options(
        selectinload(Thread.lead),
        selectinload(Thread.messages)
    ).where(Thread.id == thread_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_messages(
    session: AsyncSession,
    thread_id: uuid.UUID
) -> List[Message]:
    """Получает сообщения треда."""
    stmt = select(Message).options(
        selectinload(Message.ai_stats)
    ).where(Message.thread_id == thread_id).order_by(Message.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_thread_status(
    session: AsyncSession,
    thread_id: uuid.UUID,
    status: str
) -> Optional[Thread]:
    """Обновляет статус треда."""
    thread = await get_thread_by_id(session, thread_id)
    if not thread:
        return None
    thread.status = status
    await session.commit()
    await session.refresh(thread)
    return thread


# Функции для статистики

async def get_stats_overview(session: AsyncSession) -> Dict:
    """Получает общую статистику."""
    # Всего лидов
    total_leads = await session.execute(select(func.count(Lead.id)))
    total_leads_count = total_leads.scalar()
    
    # Активных тредов
    active_threads = await session.execute(
        select(func.count(Thread.id)).where(Thread.status != "CLOSED")
    )
    active_threads_count = active_threads.scalar()
    
    # Всего сообщений
    total_messages = await session.execute(select(func.count(Message.id)))
    total_messages_count = total_messages.scalar()
    
    # Средняя стоимость запроса
    avg_cost = await session.execute(
        select(func.avg(AIStats.cost)).where(AIStats.cost.isnot(None))
    )
    avg_cost_value = avg_cost.scalar() or 0.0
    
    return {
        "total_leads": total_leads_count,
        "active_threads": active_threads_count,
        "total_messages": total_messages_count,
        "avg_cost": float(avg_cost_value)
    }


async def get_stats_categories(session: AsyncSession) -> List[Dict]:
    """Получает распределение по категориям."""
    stmt = select(
        AIStats.category,
        func.count(AIStats.id).label("count")
    ).group_by(AIStats.category)
    
    result = await session.execute(stmt)
    return [{"category": row[0], "count": row[1]} for row in result.all()]


async def get_stats_timeline(
    session: AsyncSession,
    metric: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> List[Dict]:
    """Получает динамику по дням с заполнением пропущенных дней нулями."""
    if not date_from:
        date_from = datetime.utcnow() - timedelta(days=30)
    if not date_to:
        date_to = datetime.utcnow()
    
    # Нормализуем даты (убираем время)
    date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
    date_to = date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    if metric == "leads":
        stmt = select(
            func.date(Lead.last_seen).label("date"),
            func.count(Lead.id).label("count")
        ).where(
            and_(
                Lead.last_seen >= date_from,
                Lead.last_seen <= date_to
            )
        ).group_by(func.date(Lead.last_seen)).order_by(func.date(Lead.last_seen))
    elif metric == "messages":
        stmt = select(
            func.date(Message.created_at).label("date"),
            func.count(Message.id).label("count")
        ).where(
            and_(
                Message.created_at >= date_from,
                Message.created_at <= date_to
            )
        ).group_by(func.date(Message.created_at)).order_by(func.date(Message.created_at))
    elif metric == "costs":
        stmt = select(
            func.date(Message.created_at).label("date"),
            func.sum(AIStats.cost).label("total_cost")
        ).join(
            AIStats, Message.id == AIStats.message_id
        ).where(
            and_(
                Message.created_at >= date_from,
                Message.created_at <= date_to,
                AIStats.cost.isnot(None)
            )
        ).group_by(func.date(Message.created_at)).order_by(func.date(Message.created_at))
    else:
        return []
    
    result = await session.execute(stmt)
    data_dict = {str(row[0]): row[1] or 0 for row in result.all()}
    
    # Заполняем пропущенные дни нулями
    filled_data = []
    current_date = date_from.date()
    end_date = date_to.date()
    
    while current_date <= end_date:
        date_str = str(current_date)
        filled_data.append({
            "date": date_str,
            "value": data_dict.get(date_str, 0)
        })
        current_date += timedelta(days=1)
    
    return filled_data


async def get_stats_funnel(session: AsyncSession) -> List[Dict]:
    """Получает воронку конверсий."""
    # SPAM -> ORDER_LEAD -> HUMAN_NEEDED
    spam_count = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "SPAM")
    )
    order_lead_count = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "ORDER_LEAD")
    )
    human_needed_count = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "HUMAN_NEEDED")
    )
    
    return [
        {"stage": "SPAM", "count": spam_count.scalar()},
        {"stage": "ORDER_LEAD", "count": order_lead_count.scalar()},
        {"stage": "HUMAN_NEEDED", "count": human_needed_count.scalar()}
    ]


async def get_stats_costs(session: AsyncSession) -> Dict:
    """Получает статистику по стоимости API."""
    total_cost = await session.execute(
        select(func.sum(AIStats.cost)).where(AIStats.cost.isnot(None))
    )
    total_cost_value = total_cost.scalar() or 0.0
    
    avg_cost = await session.execute(
        select(func.avg(AIStats.cost)).where(AIStats.cost.isnot(None))
    )
    avg_cost_value = avg_cost.scalar() or 0.0
    
    return {
        "total": float(total_cost_value),
        "average": float(avg_cost_value)
    }


# Бизнес-метрики для демонстрации ценности системы

async def get_business_metrics(session: AsyncSession) -> Dict:
    """Получает бизнес-метрики для демонстрации ценности AI агента."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    # Потенциальные заказы (ORDER_LEAD)
    potential_orders = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "ORDER_LEAD")
    )
    potential_orders_count = potential_orders.scalar() or 0
    
    # Новые лиды за сегодня
    new_leads_today = await session.execute(
        select(func.count(Lead.id)).where(Lead.last_seen >= today_start)
    )
    new_leads_today_count = new_leads_today.scalar() or 0
    
    # Новые лиды за неделю
    new_leads_week = await session.execute(
        select(func.count(Lead.id)).where(Lead.last_seen >= week_start)
    )
    new_leads_week_count = new_leads_week.scalar() or 0
    
    # Сообщения обработанные AI
    ai_processed_messages = await session.execute(
        select(func.count(Message.id)).where(Message.sender_role == "AI")
    )
    ai_processed_count = ai_processed_messages.scalar() or 0
    
    # Требуют человека (HUMAN_NEEDED)
    human_needed = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "HUMAN_NEEDED")
    )
    human_needed_count = human_needed.scalar() or 0
    
    # Отфильтровано спама
    spam_filtered = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "SPAM")
    )
    spam_filtered_count = spam_filtered.scalar() or 0
    
    # Всего лидов (все уникальные лиды)
    total_leads = await session.execute(select(func.count(Lead.id)))
    total_leads_count = total_leads.scalar() or 0
    
    # Лиды, которые совершили заказ (лиды с хотя бы одним ORDER_LEAD)
    # Связь: Lead -> Thread -> Message -> AIStats (где category = 'ORDER_LEAD')
    leads_with_orders = await session.execute(
        select(func.count(func.distinct(Lead.id)))
        .join(Thread, Lead.id == Thread.lead_id)
        .join(Message, Thread.id == Message.thread_id)
        .join(AIStats, Message.id == AIStats.message_id)
        .where(AIStats.category == "ORDER_LEAD")
    )
    leads_with_orders_count = leads_with_orders.scalar() or 0
    
    # Конверсия (лиды с заказами / всего лидов)
    conversion_rate = 0.0
    if total_leads_count > 0:
        conversion_rate = (leads_with_orders_count / total_leads_count) * 100

    # Bot orders (OrderSubmission)
    orders_total_count_q = await session.execute(
        select(func.count(OrderSubmission.id)).where(OrderSubmission.status == "SENT")
    )
    orders_total_count = orders_total_count_q.scalar() or 0

    orders_total_sum_q = await session.execute(
        select(func.sum(OrderSubmission.total)).where(
            and_(OrderSubmission.status == "SENT", OrderSubmission.total.isnot(None))
        )
    )
    orders_total_sum = float(orders_total_sum_q.scalar() or 0.0)

    orders_week_sum_q = await session.execute(
        select(func.sum(OrderSubmission.total)).where(
            and_(
                OrderSubmission.status == "SENT",
                OrderSubmission.total.isnot(None),
                OrderSubmission.created_at >= week_start,
            )
        )
    )
    orders_week_sum = float(orders_week_sum_q.scalar() or 0.0)
    
    return {
        "potential_orders": potential_orders_count,
        "new_leads_today": new_leads_today_count,
        "new_leads_week": new_leads_week_count,
        "ai_processed_messages": ai_processed_count,
        "human_needed_count": human_needed_count,
        "spam_filtered": spam_filtered_count,
        "conversion_rate": round(conversion_rate, 2),
        "total_leads": total_leads_count,
        "leads_with_orders": leads_with_orders_count,
        "orders_count": orders_total_count,
        "orders_total_amount": round(orders_total_sum, 2),
        "orders_total_amount_week": round(orders_week_sum, 2),
    }


async def get_channel_distribution(session: AsyncSession) -> List[Dict]:
    """Получает распределение лидов и ORDER_LEAD по каналам."""
    # Распределение лидов по каналам
    leads_by_channel = await session.execute(
        select(Lead.channel, func.count(Lead.id).label("leads_count"))
        .group_by(Lead.channel)
    )
    
    # Распределение ORDER_LEAD по каналам
    order_leads_by_channel = await session.execute(
        select(Lead.channel, func.count(AIStats.id).label("order_leads_count"))
        .join(Thread, Lead.id == Thread.lead_id)
        .join(Message, Thread.id == Message.thread_id)
        .join(AIStats, Message.id == AIStats.message_id)
        .where(AIStats.category == "ORDER_LEAD")
        .group_by(Lead.channel)
    )
    
    # Создаем словарь для ORDER_LEAD
    order_leads_dict = {row[0]: row[1] for row in order_leads_by_channel.all()}
    
    # Формируем результат
    result = []
    for row in leads_by_channel.all():
        channel = row[0]
        leads_count = row[1]
        order_leads_count = order_leads_dict.get(channel, 0)
        result.append({
            "channel": channel,
            "leads": leads_count,
            "order_leads": order_leads_count
        })
    
    return result


async def get_enhanced_funnel(session: AsyncSession) -> List[Dict]:
    """Получает расширенную воронку продаж."""
    # Всего обращений (сообщения от пользователей)
    total_interactions = await session.execute(
        select(func.count(Message.id)).where(Message.sender_role == "USER")
    )
    total_interactions_count = total_interactions.scalar() or 0
    
    # Отфильтровано спама
    spam_filtered = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "SPAM")
    )
    spam_filtered_count = spam_filtered.scalar() or 0
    
    # Потенциальные заказы (ORDER_LEAD)
    potential_orders = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "ORDER_LEAD")
    )
    potential_orders_count = potential_orders.scalar() or 0
    
    # Требуют человека (HUMAN_NEEDED)
    human_needed = await session.execute(
        select(func.count(AIStats.id)).where(AIStats.category == "HUMAN_NEEDED")
    )
    human_needed_count = human_needed.scalar() or 0
    
    # Активные диалоги
    active_threads = await session.execute(
        select(func.count(Thread.id)).where(Thread.status != "CLOSED")
    )
    active_threads_count = active_threads.scalar() or 0
    
    return [
        {"stage": "Всего обращений", "count": total_interactions_count},
        {"stage": "Отфильтровано спама", "count": spam_filtered_count},
        {"stage": "Потенциальные заказы", "count": potential_orders_count},
        {"stage": "Требуют человека", "count": human_needed_count},
        {"stage": "Активные диалоги", "count": active_threads_count}
    ]


async def get_order_leads_timeline(
    session: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> List[Dict]:
    """Получает динамику ORDER_LEAD по дням."""
    if not date_from:
        date_from = datetime.utcnow() - timedelta(days=30)
    if not date_to:
        date_to = datetime.utcnow()
    
    stmt = select(
        func.date(Message.created_at).label("date"),
        func.count(AIStats.id).label("count")
    ).join(
        AIStats, Message.id == AIStats.message_id
    ).where(
        and_(
            Message.created_at >= date_from,
            Message.created_at <= date_to,
            AIStats.category == "ORDER_LEAD"
        )
    ).group_by(func.date(Message.created_at)).order_by(func.date(Message.created_at))
    
    result = await session.execute(stmt)
    return [{"date": str(row[0]), "value": row[1] or 0} for row in result.all()]


# Функции для работы с промптом и БЗ

async def get_active_prompt_config(session: AsyncSession) -> Optional[PromptConfig]:
    """Получает активную конфигурацию промпта."""
    stmt = select(PromptConfig).where(PromptConfig.is_active == True).order_by(desc(PromptConfig.created_at))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_prompt_config(
    session: AsyncSession,
    content: str,
    name: str = "default"
) -> PromptConfig:
    """Создает новую конфигурацию промпта."""
    # Деактивируем все предыдущие
    previous_stmt = select(PromptConfig).where(PromptConfig.is_active == True)
    previous_result = await session.execute(previous_stmt)
    for config in previous_result.scalars().all():
        config.is_active = False
    
    # Получаем следующую версию
    max_version = await session.execute(
        select(func.max(PromptConfig.version)).where(PromptConfig.name == name)
    )
    next_version = (max_version.scalar() or 0) + 1
    
    # Создаем новую конфигурацию
    config = PromptConfig(
        name=name,
        version=next_version,
        content=content,
        is_active=True
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


# Функции для работы с пользователями

async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """Получает пользователя по username."""
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Получает пользователя по email."""
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    username: str,
    email: str,
    hashed_password: str,
    full_name: Optional[str] = None,
    role: str = "manager",
) -> User:
    """Создает нового пользователя."""
    # Проверяем, что username и email уникальны
    existing_user = await get_user_by_username(session, username)
    if existing_user:
        raise ValueError(f"Username {username} already exists")
    
    if email:
        existing_email = await get_user_by_email(session, email)
        if existing_email:
            raise ValueError(f"Email {email} already exists")
    
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name
        ,role=role
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_last_login(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Обновляет время последнего входа пользователя."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        user.last_login = datetime.utcnow()
        await session.commit()


async def update_user_password(session: AsyncSession, user_id: uuid.UUID, hashed_password: str) -> Optional[User]:
    """Обновляет пароль пользователя (хранится как bcrypt hash)."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.hashed_password = hashed_password
    await session.commit()
    await session.refresh(user)
    return user


# Функции для работы с настройками
async def get_settings(session: AsyncSession, key: str = "system") -> Optional[Settings]:
    """Получает настройки по ключу."""
    stmt = select(Settings).where(Settings.key == key)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_settings(session: AsyncSession, key: str, value: dict) -> Settings:
    """Создает или обновляет настройки."""
    existing = await get_settings(session, key)
    if existing:
        existing.value = value
        existing.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(existing)
        return existing
    else:
        settings = Settings(key=key, value=value)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
        return settings

