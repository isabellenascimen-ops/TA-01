"""
Análogo ao Teste de Reinicialização (#43/#171 da spec): a trajetória deve
sobreviver ao encerramento do processo e a uma nova conexão com o banco —
não apenas aos objetos Python em memória.

Diferente dos outros testes, este NÃO usa a fixture `session` transacional
(que sempre faz rollback) — ele faz commits reais, cria um engine/conexão
TOTALMENTE NOVO para simular "reiniciar o sistema", e limpa os próprios
dados no final para permanecer idempotente.
"""
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agent.actions import Action
from app.agent.deliberation import DeliberationTrace, deliberate
from app.agent.state import AgentState
from app.llm.providers.local_stub_provider import LocalStubProvider
from app.memory.embeddings import LocalHashEmbeddingProvider
from app.memory.episodic import Episode


@pytest.mark.asyncio
async def test_trajetoria_sobrevive_a_reinicializacao_simulada(_engine):
    llm = LocalStubProvider()
    embedder = LocalHashEmbeddingProvider(dimension=256)
    SessionA = async_sessionmaker(bind=_engine, expire_on_commit=False)

    # --- "Antes de reiniciar" ---
    async with SessionA() as session_before:
        agent = AgentState(name=None, self_description="")
        session_before.add(agent)
        await session_before.flush()
        agent_id = agent.agent_id

        result = await deliberate(
            session_before,
            agent_state=agent,
            llm=llm,
            embedder=embedder,
            raw_input="lembre-se que este teste valida continuidade",
        )
        assert result.chosen_action == Action.REMEMBER
        trace_id = result.trace_id
        episode_id = result.resulting_episode_id

        await session_before.commit()  # commit real — não é rollback de teste

    # --- Simula reinicialização: nova sessão, nenhum objeto Python reaproveitado ---
    SessionB = async_sessionmaker(bind=_engine, expire_on_commit=False)
    async with SessionB() as session_after:
        reloaded_agent = await session_after.get(AgentState, agent_id)
        reloaded_episode = await session_after.get(Episode, episode_id)
        reloaded_trace = await session_after.get(DeliberationTrace, trace_id)

        assert reloaded_agent is not None
        assert reloaded_episode is not None
        assert "continuidade" in reloaded_episode.content
        assert reloaded_trace is not None
        assert reloaded_trace.chosen_action == "REMEMBER"

        # --- limpeza (mantém o teste idempotente em execuções repetidas) ---
        await session_after.execute(delete(DeliberationTrace).where(DeliberationTrace.id == trace_id))
        await session_after.execute(delete(Episode).where(Episode.id == episode_id))
        await session_after.execute(delete(AgentState).where(AgentState.agent_id == agent_id))
        await session_after.commit()
