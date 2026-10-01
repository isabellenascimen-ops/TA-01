"""
LocalStubProvider — implementação determinística de LLMProvider.

Existe por um motivo específico da spec: testes de comportamento do
agente (silêncio, iniciativa, discordância, etc. — seções 42-50) não
podem depender de um LLM real não-determinístico (ver ADR-012). Este
provedor NÃO tenta simular uma "personalidade" — ele é deliberadamente
burro e previsível, para que os testes verifiquem a ORQUESTRAÇÃO
(app/agent/deliberation.py), não a qualidade da geração de texto.

Contrato esperado pela deliberação: retornar um JSON (string) com uma
lista de candidatos:
    [{"action": "RESPOND", "content": "...", "reasoning": "..."}, ...]
"""
from __future__ import annotations

import json

from app.llm.base import LLMMessage, LLMResponse


class LocalStubProvider:
    async def generate(self, *, system: str, messages: list[LLMMessage]) -> LLMResponse:
        last_user_text = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user_text = m.content
                break

        candidates: list[dict] = []
        stripped = last_user_text.strip()

        if not stripped:
            # Seção 22: WAIT é uma ação legítima, não uma falha.
            candidates.append(
                {
                    "action": "WAIT",
                    "content": None,
                    "reasoning": "Entrada vazia — não há motivo suficiente para responder.",
                }
            )
        else:
            lowered = stripped.lower()
            if "lembre" in lowered or "remember" in lowered or "guarda isso" in lowered:
                candidates.append(
                    {
                        "action": "REMEMBER",
                        "content": stripped,
                        "reasoning": "Usuário pediu explicitamente para memorizar algo.",
                    }
                )
            candidates.append(
                {
                    "action": "RESPOND",
                    "content": f"[stub] Recebi: {stripped[:80]}",
                    "reasoning": "Entrada não trivial recebida; gerar uma resposta.",
                }
            )
            candidates.append(
                {
                    "action": "WAIT",
                    "content": None,
                    "reasoning": "Candidato de baixa prioridade, sempre disponível para comparação.",
                }
            )

        return LLMResponse(text=json.dumps(candidates, ensure_ascii=False), raw={"stub": True})
