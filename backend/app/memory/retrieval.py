"""
Recuperação híbrida de memória: similaridade semântica + recência + importância.

Seção 10: "A recuperação deverá ser híbrida ... Não utilizar somente os
últimos N textos." Seção 176: "recuperar somente informações relevantes.
Não inserir todo o banco de dados no contexto do LLM."

O componente "relação com o contexto atual" (quarto termo da fórmula da
seção 10) depende do modelo de relações, que só existe a partir de uma
fase posterior — por isso o peso w4 existe na assinatura da função desde
já (para não exigir mudar a assinatura depois), mas seu valor é 0.0 nesta
fase e isso está documentado, não escondido.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.episodic import Episode


@dataclass(frozen=True)
class RetrievalWeights:
    semantic: float = 0.45
    recency: float = 0.25
    importance: float = 0.30
    context_relation: float = 0.0  # ativado em fase futura (modelo de relações)


@dataclass(frozen=True)
class ScoredEpisode:
    episode: Episode
    score: float
    semantic_similarity: float
    recency_score: float


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _recency_score(timestamp: datetime, *, half_life_hours: float = 72.0) -> float:
    """Decaimento exponencial: memórias recentes pesam mais, nada é zerado abruptamente."""
    now = datetime.now(timezone.utc)
    ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
    return 0.5 ** (age_hours / half_life_hours)


async def retrieve_relevant_episodes(
    session: AsyncSession,
    *,
    agent_id: uuid.UUID,
    query_embedding: list[float],
    limit: int = 8,
    weights: RetrievalWeights = RetrievalWeights(),
    candidate_pool_size: int = 200,
) -> list[ScoredEpisode]:
    """
    Busca um pool de episódios recentes do agente e ranqueia por score
    híbrido. candidate_pool_size limita quantas linhas saem do banco antes
    do ranking em Python — evita "inserir todo o banco de dados" mesmo
    antes de aplicar o corte final (seção 176).
    """
    stmt = (
        select(Episode)
        .where(Episode.agent_id == agent_id)
        .order_by(Episode.timestamp.desc())
        .limit(candidate_pool_size)
    )
    result = await session.execute(stmt)
    episodes = list(result.scalars().all())

    scored: list[ScoredEpisode] = []
    for ep in episodes:
        # `is not None` explícito: o pgvector devolve numpy.ndarray, cuja
        # avaliação booleana levanta ValueError ("truth value of an array is
        # ambiguous"). Nunca usar `if ep.embedding:` aqui.
        stored = list(ep.embedding) if ep.embedding is not None else None
        sem_sim = _cosine_similarity(query_embedding, stored) if stored else 0.0
        rec = _recency_score(ep.timestamp)
        score = (
            weights.semantic * sem_sim
            + weights.recency * rec
            + weights.importance * ep.importance
            # weights.context_relation * 0.0 — reservado, ver docstring
        )
        scored.append(ScoredEpisode(episode=ep, score=score, semantic_similarity=sem_sim, recency_score=rec))

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]
