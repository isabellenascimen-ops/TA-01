"""
Pipeline de deliberação — o núcleo do agente.

Implementa o fluxo da seção 20/99, em estágios explícitos e testáveis
individualmente (ADR-005): nunca "entrada → resposta" direto.

    interpretar → recuperar memória → montar contexto → gerar candidatos
    → avaliar → decidir → registrar traço → executar

Cada execução produz OBRIGATORIAMENTE um DeliberationTrace (seção 11:
observabilidade — reconstruir o que aconteceu, quais memórias eram
relevantes, quais opções foram consideradas, qual foi escolhida).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.agent.actions import PHASE_AVAILABLE_ACTIONS, Action, ActionNotAvailableInPhaseError
from app.agent.state import AgentState
from app.database import Base
from app.llm.base import LLMMessage, LLMProvider
from app.memory.embeddings import EmbeddingProvider
from app.memory.episodic import Episode, MemoryStatus, SourceType
from app.memory.retrieval import ScoredEpisode, retrieve_relevant_episodes

# Ordem de prioridade para desempate determinístico em evaluate_candidates/decide.
_PRIORITY_ORDER: dict[Action, int] = {
    Action.RESPOND: 0,
    Action.REMEMBER: 1,
    Action.WAIT: 2,
}


class DeliberationTrace(Base):
    """Registro imutável de UMA execução do pipeline."""

    __tablename__ = "deliberation_trace"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_state.agent_id"),
        nullable=False,
        index=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    input_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    state_snapshot_ref: Mapped[int] = mapped_column(
        Float,
        nullable=False,
    )

    memories_considered: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
    )

    candidates_considered: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    evaluation_scores: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    chosen_action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    resulting_episode_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("episode.id"),
        nullable=True,
    )


@dataclass(frozen=True)
class Candidate:
    action: Action
    content: str | None
    reasoning: str


@dataclass(frozen=True)
class DeliberationResult:
    trace_id: uuid.UUID
    chosen_action: Action
    response_text: str | None
    resulting_episode_id: uuid.UUID | None


# --- Estágio 1: interpretar -------------------------------------------------


def interpret_input(raw_text: str) -> str:
    """Fase 1: interpretação mínima."""
    return raw_text.strip()


# --- Estágio 2: montar contexto --------------------------------------------


def build_system_prompt(
    agent_state: AgentState,
    retrieved: list[ScoredEpisode],
) -> str:
    name = agent_state.name or "(ainda sem nome)"

    lines = [
        "Você é o núcleo de deliberação de um agente de trajetória persistente.",
        f"Nome atual do agente: {name}",
        f"Autodescrição atual: {agent_state.self_description or '(vazia)'}",
        "",
        "Ações disponíveis nesta fase do projeto: "
        + ", ".join(a.value for a in PHASE_AVAILABLE_ACTIONS),
        "",
        "Memórias relevantes recuperadas:",
    ]

    if retrieved:
        for s in retrieved:
            lines.append(
                f"- ({s.episode.timestamp.isoformat()}) "
                f"{s.episode.content}"
            )
    else:
        lines.append("- (nenhuma memória relevante encontrada)")

    lines.append("")

    lines.append(
        "Responda APENAS com um array JSON de candidatos, cada um com "
        '"action", "content" e "reasoning". Não inclua nada fora do JSON.'
    )

    return "\n".join(lines)


# --- Estágio 3: gerar candidatos ---------------------------------------------


async def generate_candidates(
    llm: LLMProvider,
    system_prompt: str,
    user_input: str,
) -> tuple[list[Candidate], str]:

    response = await llm.generate(
        system=system_prompt,
        messages=[
            LLMMessage(
                role="user",
                content=user_input,
            )
        ],
    )

    raw_text = response.text

    # DEBUG TEMPORÁRIO
    print("=== QWEN RAW ===")
    print(raw_text)
    print("=== END QWEN RAW ===")

    candidates: list[Candidate] = []

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = []

    # O Ollama pode retornar:
    # {"candidates": [...]}
    # enquanto o pipeline original esperava diretamente:
    # [...]
    if isinstance(parsed, dict):
        parsed = parsed.get("candidates", [])

    for item in parsed if isinstance(parsed, list) else []:
        try:
            action = Action(item.get("action"))
        except ValueError:
            continue

        candidates.append(
            Candidate(
                action=action,
                content=item.get("content"),
                reasoning=item.get("reasoning", ""),
            )
        )

    if not candidates:
        candidates.append(
            Candidate(
                action=Action.WAIT,
                content=None,
                reasoning="Nenhum candidato válido gerado.",
            )
        )

    return candidates, raw_text


# --- Estágio 4: avaliar -------------------------------------------------------


_EXPLICIT_MEMORY_MARKERS: tuple[str, ...] = (
    "lembre",
    "lembra",
    "memorize",
    "guarda isso",
    "guarde isso",
    "não esqueça",
    "nao esqueca",
    "anote",
    "remember",
)


def has_explicit_memory_request(raw_input: str) -> bool:
    lowered = raw_input.lower()

    return any(
        marker in lowered
        for marker in _EXPLICIT_MEMORY_MARKERS
    )


def evaluate_candidates(
    candidates: list[Candidate],
    raw_input: str,
) -> dict[Action, float]:

    explicit_memory = has_explicit_memory_request(raw_input)

    scores: dict[Action, float] = {}

    for c in candidates:

        if c.action not in PHASE_AVAILABLE_ACTIONS:
            scores[c.action] = 0.0
            continue

        if c.action == Action.WAIT:
            scores[c.action] = (
                0.9 if not raw_input.strip() else 0.2
            )

        elif c.action == Action.RESPOND:
            has_content = bool(
                c.content and c.content.strip()
            )

            scores[c.action] = (
                0.75 if has_content else 0.4
            )

        elif c.action == Action.REMEMBER:

            if not (c.content and c.content.strip()):
                scores[c.action] = 0.1

            else:
                scores[c.action] = (
                    0.85 if explicit_memory else 0.55
                )

        else:
            scores[c.action] = 0.0

    return scores


# --- Estágio 5: decidir --------------------------------------------------------


def decide(
    candidates: list[Candidate],
    scores: dict[Action, float],
) -> Candidate:

    available = [
        c
        for c in candidates
        if c.action in PHASE_AVAILABLE_ACTIONS
    ]

    if not available:
        return Candidate(
            action=Action.WAIT,
            content=None,
            reasoning="Nenhum candidato disponível nesta fase.",
        )

    available.sort(
        key=lambda c: (
            -scores.get(c.action, 0.0),
            _PRIORITY_ORDER.get(c.action, 99),
        )
    )

    return available[0]


# --- Estágio 6: executar -------------------------------------------------------


async def _store_episode(
    session: AsyncSession,
    *,
    agent_id: uuid.UUID,
    embedder: EmbeddingProvider,
    event_type: str,
    content: str,
    interpretation: str | None,
    importance: float,
) -> Episode:

    embedding = await embedder.embed(content)

    episode = Episode(
        agent_id=agent_id,
        event_type=event_type,
        content=content,
        interpretation=interpretation,
        importance=importance,
        participants=[],
        embedding=embedding,
        source_type=SourceType.SYSTEM_EVENT,
        source_id="deliberation_pipeline",
        confidence=1.0,
        status=MemoryStatus.OBSERVED,
    )

    session.add(episode)

    await session.flush()

    return episode


async def execute_action(
    session: AsyncSession,
    *,
    agent_state: AgentState,
    embedder: EmbeddingProvider,
    chosen: Candidate,
    raw_input: str,
) -> tuple[str | None, Episode | None]:

    if chosen.action not in PHASE_AVAILABLE_ACTIONS:
        raise ActionNotAvailableInPhaseError(chosen.action)

    if chosen.action == Action.WAIT:

        episode = await _store_episode(
            session,
            agent_id=agent_state.agent_id,
            embedder=embedder,
            event_type="wait",
            content=f"Entrada recebida: {raw_input!r}. Decisão: esperar.",
            interpretation=chosen.reasoning,
            importance=0.05,
        )

        return None, episode

    if chosen.action == Action.RESPOND:

        response_text = chosen.content or ""

        episode = await _store_episode(
            session,
            agent_id=agent_state.agent_id,
            embedder=embedder,
            event_type="conversation",
            content=f"user: {raw_input}\nagent: {response_text}",
            interpretation=chosen.reasoning,
            importance=0.35,
        )

        return response_text, episode

    if chosen.action == Action.REMEMBER:

        fact_text = chosen.content or raw_input

        episode = await _store_episode(
            session,
            agent_id=agent_state.agent_id,
            embedder=embedder,
            event_type="explicit_memory_request",
            content=fact_text,
            interpretation=chosen.reasoning,
            importance=0.75,
        )

        return f"Memorizado: {fact_text}", episode

    raise ActionNotAvailableInPhaseError(chosen.action)


# --- Orquestrador --------------------------------------------------------------


async def deliberate(
    session: AsyncSession,
    *,
    agent_state: AgentState,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    raw_input: str,
) -> DeliberationResult:

    interpreted = interpret_input(raw_input)

    query_embedding = (
        await embedder.embed(interpreted)
        if interpreted
        else [0.0] * embedder.dimension
    )

    retrieved = await retrieve_relevant_episodes(
        session,
        agent_id=agent_state.agent_id,
        query_embedding=query_embedding,
    )

    system_prompt = build_system_prompt(
        agent_state,
        retrieved,
    )

    candidates, raw_llm_output = await generate_candidates(
        llm,
        system_prompt,
        interpreted,
    )

    scores = evaluate_candidates(
        candidates,
        interpreted,
    )

    chosen = decide(
        candidates,
        scores,
    )

    response_text, episode = await execute_action(
        session,
        agent_state=agent_state,
        embedder=embedder,
        chosen=chosen,
        raw_input=interpreted,
    )

    trace = DeliberationTrace(
        agent_id=agent_state.agent_id,
        input_summary=interpreted[:500],
        state_snapshot_ref=float(agent_state.version),
        memories_considered=[
            str(s.episode.id)
            for s in retrieved
        ],
        candidates_considered={
            "raw_llm_output": raw_llm_output,
            "parsed": [
                {
                    "action": c.action.value,
                    "content": c.content,
                    "reasoning": c.reasoning,
                }
                for c in candidates
            ],
        },
        evaluation_scores={
            a.value: s
            for a, s in scores.items()
        },
        chosen_action=chosen.action.value,
        result=response_text,
        resulting_episode_id=(
            episode.id
            if episode
            else None
        ),
    )

    session.add(trace)

    await session.flush()

    return DeliberationResult(
        trace_id=trace.id,
        chosen_action=chosen.action,
        response_text=response_text,
        resulting_episode_id=(
            episode.id
            if episode
            else None
        ),
    )