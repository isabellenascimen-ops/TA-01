"""
Fixtures compartilhadas.

Testes de integração/scenario usam o banco `trajectory_test` (Postgres real
com pgvector), não SQLite e não mocks de banco — porque parte do que
estamos testando é justamente a persistência real (pgvector, JSONB,
foreign keys, enums). Cada teste roda dentro de uma transação que é
revertida no final, então os testes não interferem entre si.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://trajectory:trajectory_dev_pw@localhost:5432/trajectory_test"
)

from app.agent.state import AgentState  # noqa: E402
from app.models import Base  # noqa: E402

TEST_DATABASE_URL = "postgresql+asyncpg://trajectory:trajectory_dev_pw@localhost:5432/trajectory_test"


@pytest_asyncio.fixture()
async def _engine():
    # Escopo por-teste (não "session"): pytest-asyncio cria um event loop novo
    # por teste por padrão, e conexões asyncpg não podem atravessar loops —
    # reutilizar um engine "session-scoped" causa
    # "InterfaceError: another operation is in progress" de forma intermitente.
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def session(_engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await _engine.connect()
    trans = await connection.begin()
    # join_transaction_mode="create_savepoint": a sessão usa SAVEPOINTs por
    # baixo dos panos, então mesmo que o código do app chame session.commit()
    # (como app/api faz) ou a sessão precise de rollback após um erro de
    # flush, a transação EXTERNA (trans) continua íntegra e o rollback final
    # desfaz tudo. É o padrão recomendado pela própria documentação do
    # SQLAlchemy 2.0 para isolar testes com um Postgres real.
    session_factory = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    async_session = session_factory()

    yield async_session

    await async_session.close()
    await trans.rollback()
    await connection.close()


@pytest_asyncio.fixture()
async def agent_state(session: AsyncSession) -> AgentState:
    agent = AgentState()
    session.add(agent)
    await session.flush()
    return agent
