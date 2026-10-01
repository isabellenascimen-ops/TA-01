"""
Testes de integração contra Postgres real (com pgvector habilitado) —
não SQLite, não mocks. Isso valida o schema de verdade: enums do
Postgres, coluna vector(256), JSONB, foreign keys.
"""
import uuid

import pytest
from sqlalchemy import select

from app.agent.state import AgentState
from app.memory.episodic import Episode, MemoryStatus, SourceType


@pytest.mark.asyncio
async def test_agent_state_starts_with_minimal_identity(session, agent_state):
    """Seção 2 da spec: nome=inexistente, autodescrição=vazia."""
    assert agent_state.name is None
    assert agent_state.self_description == ""
    assert agent_state.version == 1


@pytest.mark.asyncio
async def test_episode_roundtrip_with_real_pgvector_embedding(session, agent_state):
    embedding = [0.1] * 256
    episode = Episode(
        agent_id=agent_state.agent_id,
        event_type="conversation",
        content="Primeira conversa de teste.",
        interpretation="Teste de integração.",
        importance=0.5,
        participants=[],
        embedding=embedding,
        source_type=SourceType.SYSTEM_EVENT,
        source_id="test",
        confidence=1.0,
        status=MemoryStatus.OBSERVED,
    )
    session.add(episode)
    await session.flush()

    fetched = await session.get(Episode, episode.id)
    assert fetched is not None
    assert fetched.content == "Primeira conversa de teste."
    assert fetched.status == MemoryStatus.OBSERVED
    assert fetched.source_type == SourceType.SYSTEM_EVENT
    # pgvector devolve o vetor como lista/array de floats do mesmo tamanho
    assert len(fetched.embedding) == 256


@pytest.mark.asyncio
async def test_episode_requires_agent_foreign_key(session):
    """Nenhum episódio pode existir sem um agente — sem 'user' universal (seção 183, aplicado a agentes)."""
    from sqlalchemy.exc import IntegrityError

    orphan = Episode(
        agent_id=uuid.uuid4(),  # agente inexistente
        event_type="conversation",
        content="Órfão",
        importance=0.1,
        participants=[],
        source_type=SourceType.SYSTEM_EVENT,
        source_id="test",
        confidence=1.0,
        status=MemoryStatus.UNKNOWN,
    )
    session.add(orphan)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()  # necessário após um flush que falhou, antes de reusar a sessão
