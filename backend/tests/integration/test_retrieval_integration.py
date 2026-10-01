import pytest

from app.memory.embeddings import LocalHashEmbeddingProvider
from app.memory.episodic import Episode, MemoryStatus, SourceType
from app.memory.retrieval import retrieve_relevant_episodes


async def _add_episode(session, agent_state, *, content: str, importance: float, embedding):
    ep = Episode(
        agent_id=agent_state.agent_id,
        event_type="conversation",
        content=content,
        importance=importance,
        participants=[],
        embedding=embedding,
        source_type=SourceType.SYSTEM_EVENT,
        source_id="test",
        confidence=1.0,
        status=MemoryStatus.OBSERVED,
    )
    session.add(ep)
    await session.flush()
    return ep


@pytest.mark.asyncio
async def test_retrieval_ranks_semantically_similar_episode_higher(session, agent_state):
    embedder = LocalHashEmbeddingProvider(dimension=256)

    similar_text = "identidade artificial e continuidade"
    unrelated_text = "receita de bolo de chocolate"

    similar_embedding = await embedder.embed(similar_text)
    unrelated_embedding = await embedder.embed(unrelated_text)

    await _add_episode(session, agent_state, content=similar_text, importance=0.3, embedding=similar_embedding)
    await _add_episode(session, agent_state, content=unrelated_text, importance=0.3, embedding=unrelated_embedding)

    query_embedding = await embedder.embed("identidade e continuidade da IA")
    results = await retrieve_relevant_episodes(
        session, agent_id=agent_state.agent_id, query_embedding=query_embedding, limit=5
    )

    assert len(results) == 2
    assert results[0].episode.content == similar_text
    assert results[0].semantic_similarity >= results[1].semantic_similarity


@pytest.mark.asyncio
async def test_retrieval_is_scoped_to_agent(session, agent_state):
    """Nunca misturar memórias de agentes diferentes (isolamento, base para seção 184/185)."""
    from app.agent.state import AgentState

    other_agent = AgentState()
    session.add(other_agent)
    await session.flush()

    embedder = LocalHashEmbeddingProvider(dimension=256)
    emb = await embedder.embed("memória do outro agente")
    await _add_episode(session, other_agent, content="memória do outro agente", importance=0.9, embedding=emb)

    results = await retrieve_relevant_episodes(
        session, agent_id=agent_state.agent_id, query_embedding=emb, limit=5
    )
    assert results == []
