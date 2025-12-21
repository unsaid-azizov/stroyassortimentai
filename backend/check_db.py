#!/usr/bin/env python3
"""Скрипт для проверки подключения к PostgreSQL"""
import asyncio
import sys
from sqlalchemy import text
from db.session import engine

async def check_db():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("PostgreSQL готов!")
        return True
    except Exception as e:
        print(f"PostgreSQL еще не готов: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = asyncio.run(check_db())
    sys.exit(0 if success else 1)

