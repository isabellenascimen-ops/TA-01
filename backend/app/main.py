from __future__ import annotations

from fastapi import FastAPI

from app.api import agent as agent_router
from app.api import chat as chat_router

app = FastAPI(
    title="TA-01 — Trajectory Agent",
    version="0.1.0-phase1",
    description=(
        "Fase 1: AgentState, memória episódica básica, LLMProvider "
        "(stub + Anthropic) e pipeline mínimo de deliberação. "
        "Sem ciclo autônomo, ferramentas, relações ou export/import ainda."
    ),
)

app.include_router(agent_router.router)
app.include_router(chat_router.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "phase": 1}
