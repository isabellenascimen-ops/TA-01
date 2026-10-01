"""
Cenários de comportamento do agente, mapeados diretamente à spec.
Usam LocalStubProvider (determinístico) + Postgres real — nunca um LLM
real (ver ADR-012: testes de CI não dependem de julgamento sobre texto
gerado por um LLM não-determinístico).
"""
import pytest

from app.agent.actions import Action
from app.agent.deliberation import DeliberationTrace, deliberate
from app.llm.providers.local_stub_provider import LocalStubProvider
from app.memory.embeddings import LocalHashEmbeddingProvider
from app.memory.episodic import Episode


@pytest.fixture
def llm():
    return LocalStubProvider()


@pytest.fixture
def embedder():
    return LocalHashEmbeddingProvider(dimension=256)


@pytest.mark.asyncio
async def test_scenario_silencio_entrada_vazia_resulta_em_wait(session, agent_state, llm, embedder):
    """Análogo ao Teste de Silêncio (#46): esperar é um resultado válido, não uma falha."""
    result = await deliberate(session, agent_state=agent_state, llm=llm, embedder=embedder, raw_input="   ")

    assert result.chosen_action == Action.WAIT
    assert result.response_text is None

    trace = await session.get(DeliberationTrace, result.trace_id)
    assert trace is not None
    assert trace.chosen_action == "WAIT"


@pytest.mark.asyncio
async def test_scenario_entrada_normal_gera_resposta_e_memoria(session, agent_state, llm, embedder):
    result = await deliberate(
        session, agent_state=agent_state, llm=llm, embedder=embedder, raw_input="Olá, quem é você?"
    )

    assert result.chosen_action == Action.RESPOND
    assert result.response_text is not None
    assert result.resulting_episode_id is not None

    episode = await session.get(Episode, result.resulting_episode_id)
    assert episode is not None
    assert "Olá, quem é você?" in episode.content


@pytest.mark.asyncio
async def test_scenario_pedido_explicito_de_memorizacao(session, agent_state, llm, embedder):
    result = await deliberate(
        session,
        agent_state=agent_state,
        llm=llm,
        embedder=embedder,
        raw_input="lembre-se que meu aniversário é em outubro",
    )

    assert result.chosen_action == Action.REMEMBER
    episode = await session.get(Episode, result.resulting_episode_id)
    assert "aniversário" in episode.content
    assert episode.importance > 0.5  # memórias explícitas pesam mais que conversa comum


@pytest.mark.asyncio
async def test_scenario_toda_deliberacao_produz_traco_observavel(session, agent_state, llm, embedder):
    """Seção 11: reconstruir o que aconteceu, quais memórias eram relevantes, o que foi decidido."""
    result = await deliberate(
        session, agent_state=agent_state, llm=llm, embedder=embedder, raw_input="Teste de observabilidade."
    )

    trace = await session.get(DeliberationTrace, result.trace_id)
    assert trace.input_summary == "Teste de observabilidade."
    assert "parsed" in trace.candidates_considered
    assert len(trace.candidates_considered["parsed"]) >= 1
    assert trace.evaluation_scores  # nenhuma decisão sem pontuação registrada
    assert trace.chosen_action == result.chosen_action.value
