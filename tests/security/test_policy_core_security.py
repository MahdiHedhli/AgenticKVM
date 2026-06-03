from agentickvm.control_plane import ControlMode, PolicyDecision, mode_preset


def test_missing_target_scope_denies_dangerous_provider_actions() -> None:
    policy = mode_preset(ControlMode.SUPERVISED)

    result = policy.decision_for("power.force_off", session_id="s1")

    assert result.decision == PolicyDecision.DENY
    assert result.reason == "missing required target scope"


def test_missing_session_scope_denies_provider_actions() -> None:
    policy = mode_preset(ControlMode.SUPERVISED)

    result = policy.decision_for("observe.status", target_id="lab-a")

    assert result.decision == PolicyDecision.DENY
    assert result.reason == "missing required session scope"


def test_full_control_keeps_hard_invariants() -> None:
    policy = mode_preset(ControlMode.FULL_CONTROL)

    for capability_id in {
        "session.modify_policy",
        "session.disable_audit",
        "session.disable_emergency_stop",
    }:
        result = policy.decision_for(capability_id, session_id="s1")

        assert result.decision == PolicyDecision.DENY
        assert result.reason == "hard invariant"


def test_full_control_bypasses_prompts_not_scope() -> None:
    policy = mode_preset(ControlMode.FULL_CONTROL)

    scoped = policy.decision_for(
        "power.force_off",
        target_id="lab-a",
        session_id="s1",
    )
    unscoped = policy.decision_for("power.force_off", session_id="s1")

    assert scoped.decision == PolicyDecision.ALLOW
    assert unscoped.decision == PolicyDecision.DENY
    assert unscoped.reason == "missing required target scope"
