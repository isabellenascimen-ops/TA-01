"""
Infraestrutura de banco de dados: engine assíncrono, fábrica de sessões e
a classe Base declarativa usada por todos os modelos ORM do projeto.

Decisão (ADR-001 em ARCHITECTURE_DECISIONS.md): pgvector vive dentro do
mesmo Postgres que o resto do estado — não existe um segundo "banco de
vetores". Por isso há apenas UM engine no projeto inteiro.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos (agent/*, memory/*)."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency do FastAPI: uma sessão por requisição, com commit/rollback explícitos."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
