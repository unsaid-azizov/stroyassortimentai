"""
Скрипт для добавления моковых данных в базу данных для демонстрации графиков.
"""
import asyncio
from datetime import datetime, timedelta
import uuid
from db.session import async_session_factory
from db.models import Lead, Thread, Message, AIStats
from sqlalchemy import select

async def add_mock_data():
    """Добавляет моковые данные за последние 10 дней."""
    async with async_session_factory() as session:
        # Генерируем данные за последние 10 дней
        today = datetime.utcnow()
        
        # Создаем лиды с разными датами
        leads_created = []
        for day_offset in range(10, 0, -1):
            date = today - timedelta(days=day_offset)
            # Создаем 2-5 лидов в день
            num_leads = 2 + (day_offset % 4)
            
            for i in range(num_leads):
                lead = Lead(
                    id=uuid.uuid4(),
                    external_id=f"mock_telegram_{day_offset}_{i}",
                    channel="telegram" if i % 2 == 0 else "email",
                    name=f"Тестовый лид {day_offset}-{i}",
                    phone=f"+799912345{day_offset}{i}",
                    email=f"test{day_offset}_{i}@example.com",
                    last_seen=date + timedelta(hours=i*2)
                )
                leads_created.append(lead)
                session.add(lead)
        
        await session.commit()
        print(f"✅ Создано {len(leads_created)} лидов")
        
        # Получаем все лиды из базы для создания потоков и сообщений
        all_leads_result = await session.execute(select(Lead))
        leads_list = all_leads_result.scalars().all()
        
        # Создаем потоки и сообщения
        threads_created = []
        messages_created = []
        ai_stats_created = []
        
        for day_offset in range(10, 0, -1):
            date = today - timedelta(days=day_offset)
            
            # Берем случайные лиды для этого дня
            day_leads = [l for l in leads_list if (today - l.last_seen).days == day_offset]
            if not day_leads:
                continue
            
            # Создаем 3-8 сообщений в день
            num_messages = 3 + (day_offset % 6)
            
            for i in range(num_messages):
                # Выбираем случайного лида
                lead = day_leads[i % len(day_leads)]
                
                # Создаем поток, если его еще нет
                thread_stmt = select(Thread).where(Thread.lead_id == lead.id).limit(1)
                thread_result = await session.execute(thread_stmt)
                thread = thread_result.scalar_one_or_none()
                
                if not thread:
                    thread = Thread(
                        id=uuid.uuid4(),
                        lead_id=lead.id,
                        status="AI_ONLY",
                        created_at=date + timedelta(hours=i)
                    )
                    session.add(thread)
                    await session.flush()
                    threads_created.append(thread)
                
                # Создаем сообщение от пользователя
                user_message = Message(
                    id=uuid.uuid4(),
                    thread_id=thread.id,
                    content=f"Тестовое сообщение {day_offset}-{i}",
                    sender_role="USER",
                    created_at=date + timedelta(hours=i, minutes=10)
                )
                session.add(user_message)
                await session.flush()
                messages_created.append(user_message)
                
                # Создаем AI статистику для некоторых сообщений
                if i % 3 == 0:  # Каждое третье сообщение
                    category = "ORDER_LEAD" if i % 5 == 0 else ("SPAM" if i % 7 == 0 else "HUMAN_NEEDED")
                    ai_stat = AIStats(
                        id=uuid.uuid4(),
                        message_id=user_message.id,
                        category=category,
                        cost=0.001 * (i + 1),
                        reasoning="Mock data for testing"
                    )
                    session.add(ai_stat)
                    ai_stats_created.append(ai_stat)
                
                # Создаем ответ от AI
                ai_message = Message(
                    id=uuid.uuid4(),
                    thread_id=thread.id,
                    content=f"Ответ AI на сообщение {day_offset}-{i}",
                    sender_role="AI",
                    created_at=date + timedelta(hours=i, minutes=15)
                )
                session.add(ai_message)
                messages_created.append(ai_message)
        
        await session.commit()
        print(f"✅ Создано {len(threads_created)} потоков")
        print(f"✅ Создано {len(messages_created)} сообщений")
        print(f"✅ Создано {len(ai_stats_created)} AI статистик")
        print(f"\n🎉 Всего добавлено моковых данных за последние 10 дней!")

if __name__ == "__main__":
    asyncio.run(add_mock_data())

