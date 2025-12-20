from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from os import getenv
from dotenv import load_dotenv

load_dotenv()

# Формат: postgresql+asyncpg://user:password@host:port/dbname
DATABASE_URL = getenv("DATABASE_URL", "postgresql+asyncpg://said:said@localhost:5432/said_crm")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async with async_session_factory() as session:
        yield session

