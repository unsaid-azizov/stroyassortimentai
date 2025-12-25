import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import async_session_factory
from db.repository import get_active_prompt_config

async def check():
    async with async_session_factory() as session:
        prompt = await get_active_prompt_config(session)
        if prompt:
            print(f"✅ Промпт найден! Длина: {len(prompt.content)} символов")
        else:
            print("❌ Промпт не найден")

if __name__ == "__main__":
    asyncio.run(check())



