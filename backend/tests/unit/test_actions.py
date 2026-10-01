from app.agent.actions import PHASE_AVAILABLE_ACTIONS, Action, ActionNotAvailableInPhaseError


def test_full_action_enum_matches_spec_section_21():
    expected = {
        "WAIT",
        "RESPOND",
        "START_CONVERSATION",
        "RESEARCH",
        "CREATE",
        "REMEMBER",
        "UPDATE_SELF",
        "UPDATE_RELATIONSHIP",
    }
    assert {a.value for a in Action} == expected


def test_phase1_only_exposes_three_actions():
    assert PHASE_AVAILABLE_ACTIONS == {Action.WAIT, Action.RESPOND, Action.REMEMBER}


def test_action_not_available_error_names_the_action():
    err = ActionNotAvailableInPhaseError(Action.START_CONVERSATION)
    assert "START_CONVERSATION" in str(err)
