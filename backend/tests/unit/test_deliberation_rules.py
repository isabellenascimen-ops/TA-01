"""
Testam apenas as REGRAS DETERMINÍSTICAS (evaluate_candidates/decide), sem
banco de dados e sem LLM — exatamente o tipo de teste que a seção 15 da
spec pede: "implementar regras determinísticas no software... testar
comportamento".
"""
from app.agent.actions import Action
from app.agent.deliberation import (
    Candidate,
    decide,
    evaluate_candidates,
    has_explicit_memory_request,
)


def test_empty_input_favours_wait():
    candidates = [
        Candidate(action=Action.WAIT, content=None, reasoning="nada a fazer"),
        Candidate(action=Action.RESPOND, content="", reasoning="tentativa vazia"),
    ]
    scores = evaluate_candidates(candidates, raw_input="")
    assert scores[Action.WAIT] > scores[Action.RESPOND]
    chosen = decide(candidates, scores)
    assert chosen.action == Action.WAIT


def test_non_trivial_input_favours_respond_over_wait():
    candidates = [
        Candidate(action=Action.WAIT, content=None, reasoning="baixa prioridade"),
        Candidate(action=Action.RESPOND, content="Olá! Como posso ajudar?", reasoning="entrada válida"),
    ]
    scores = evaluate_candidates(candidates, raw_input="Oi, tudo bem?")
    chosen = decide(candidates, scores)
    assert chosen.action == Action.RESPOND


def test_remember_request_is_scored_and_available():
    candidates = [
        Candidate(action=Action.REMEMBER, content="Alice prefere respostas diretas.", reasoning="pedido explícito"),
        Candidate(action=Action.WAIT, content=None, reasoning="fallback"),
    ]
    scores = evaluate_candidates(candidates, raw_input="lembre-se que Alice prefere respostas diretas")
    assert scores[Action.REMEMBER] > scores[Action.WAIT]
    chosen = decide(candidates, scores)
    assert chosen.action == Action.REMEMBER


def test_actions_outside_current_phase_are_scored_zero_and_never_chosen():
    """
    UPDATE_SELF existe no enum (contrato futuro) mas não tem handler nesta
    fase. Mesmo que o LLM "proponha" essa ação, ela nunca deve ser escolhida.
    """
    candidates = [
        Candidate(action=Action.UPDATE_SELF, content="mudar autodescrição", reasoning="tentativa"),
        Candidate(action=Action.WAIT, content=None, reasoning="fallback"),
    ]
    scores = evaluate_candidates(candidates, raw_input="algo")
    assert scores[Action.UPDATE_SELF] == 0.0
    chosen = decide(candidates, scores)
    assert chosen.action == Action.WAIT


def test_decide_never_crashes_on_empty_candidate_list():
    chosen = decide([], {})
    assert chosen.action == Action.WAIT


def test_explicit_memory_request_detection():
    assert has_explicit_memory_request("lembre-se que eu prefiro café")
    assert has_explicit_memory_request("Por favor, ANOTE isso")
    assert has_explicit_memory_request("remember this for later")
    assert not has_explicit_memory_request("qual é a capital da França?")


def test_explicit_request_makes_remember_outrank_respond():
    """
    Regressão: antes, REMEMBER (0.65) perdia para RESPOND (0.75) mesmo com
    pedido explícito — o agente respondia em vez de guardar o que foi pedido.
    """
    candidates = [
        Candidate(action=Action.REMEMBER, content="prefiro café sem açúcar", reasoning="pedido explícito"),
        Candidate(action=Action.RESPOND, content="Certo!", reasoning="resposta genérica"),
    ]
    scores = evaluate_candidates(candidates, raw_input="lembre-se que prefiro café sem açúcar")
    assert scores[Action.REMEMBER] > scores[Action.RESPOND]
    assert decide(candidates, scores).action == Action.REMEMBER


def test_without_explicit_request_respond_still_wins():
    """O inverso também precisa valer: sem pedido explícito, conversar é o padrão."""
    candidates = [
        Candidate(action=Action.REMEMBER, content="algo", reasoning="proposta do LLM"),
        Candidate(action=Action.RESPOND, content="Olá!", reasoning="resposta"),
    ]
    scores = evaluate_candidates(candidates, raw_input="oi, tudo bem?")
    assert scores[Action.RESPOND] > scores[Action.REMEMBER]
    assert decide(candidates, scores).action == Action.RESPOND
