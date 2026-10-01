"""
Ações que o agente pode tomar (seção 21 da especificação TA-01).

O enum completo é definido desde a Fase 1 porque ele é *contrato*, não
comportamento — mudar o contrato depois exigiria migrar dados. O que muda
fase a fase é apenas PHASE_AVAILABLE_ACTIONS: quais ações têm um handler
real implementado em app/agent/deliberation.py::execute_action().

Tentar decidir por uma ação fora da fase atual é um erro de programação
(ActionNotAvailableInPhaseError), não um caminho silencioso — nunca
queremos que o agente "finja" ter feito algo que não tem suporte ainda.
"""
from __future__ import annotations

import enum


class Action(str, enum.Enum):
    WAIT = "WAIT"
    RESPOND = "RESPOND"
    START_CONVERSATION = "START_CONVERSATION"
    RESEARCH = "RESEARCH"
    CREATE = "CREATE"
    REMEMBER = "REMEMBER"
    UPDATE_SELF = "UPDATE_SELF"
    UPDATE_RELATIONSHIP = "UPDATE_RELATIONSHIP"


# Fase 1: sem ciclo autônomo (→ sem START_CONVERSATION), sem ferramentas
# (→ sem RESEARCH/CREATE), sem modelo de relações (→ sem UPDATE_RELATIONSHIP),
# sem SelfModel/Belief/Preference ainda (→ sem UPDATE_SELF).
# Isso é o que "criar somente o necessário" (regra da spec) significa em código.
PHASE_AVAILABLE_ACTIONS: frozenset[Action] = frozenset(
    {Action.WAIT, Action.RESPOND, Action.REMEMBER}
)


class ActionNotAvailableInPhaseError(Exception):
    """Levantado quando a deliberação escolhe uma ação que ainda não tem handler."""

    def __init__(self, action: Action):
        self.action = action
        super().__init__(
            f"Ação {action.value!r} está definida no contrato (Action enum) "
            f"mas ainda não tem handler nesta fase do projeto. "
            f"Ações disponíveis agora: {sorted(a.value for a in PHASE_AVAILABLE_ACTIONS)}."
        )
