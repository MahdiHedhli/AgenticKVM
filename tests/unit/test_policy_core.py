import json

import pytest

from agentickvm.control_plane import (
    DEFAULT_CAPABILITY_REGISTRY,
    ControlMode,
    PolicyDecision,
    PolicyRule,
    SessionScope,
    TargetScope,
    load_policy_file,
    mode_preset,
)
from agentickvm.control_plane.policy import CapabilityPolicy


def test_unknown_capability_denies_in_every_mode() -> None:
    for mode in ControlMode:
        policy = mode_preset(mode)
        result = policy.decision_for("provider.raw_reset", session_id="s1")

        assert result.decision == PolicyDecision.DENY
        assert result.reason == "unknown capability"


def test_observe_mode_blocks_mutating_actions() -> None:
    policy = mode_preset(ControlMode.OBSERVE)

    allowed = policy.decision_for(
        "observe.power_state",
        target_id="lab-a",
        session_id="s1",
    )
    denied = policy.decision_for(
        "power.force_off",
        target_id="lab-a",
        session_id="s1",
    )

    assert allowed.decision == PolicyDecision.ALLOW
    assert denied.decision == PolicyDecision.DENY


def test_supervised_mode_gates_dangerous_actions() -> None:
    policy = mode_preset(ControlMode.SUPERVISED)

    result = policy.decision_for(
        "storage.wipe_disk",
        target_id="lab-a",
        session_id="s1",
    )

    assert result.decision == PolicyDecision.ASK_EACH_TIME
    assert result.requires_approval is True
    assert "dangerous action" in result.material_risks
    assert "destructive action" in result.material_risks


def test_full_control_does_not_allow_raw_secret_reveal_by_default() -> None:
    policy = mode_preset(ControlMode.FULL_CONTROL)

    result = policy.decision_for(
        "secrets.raw_reveal",
        target_id="lab-a",
        session_id="s1",
    )

    assert result.decision == PolicyDecision.DENY
    assert result.reason == "missing required credential scope"


def test_hard_invariants_deny_policy_self_modification() -> None:
    policy = CapabilityPolicy(
        name="attempted override",
        mode=ControlMode.CUSTOM,
        rules={
            "session.modify_policy": PolicyRule(decision=PolicyDecision.ALLOW),
        },
    )

    result = policy.decision_for("session.modify_policy", session_id="s1")

    assert result.decision == PolicyDecision.DENY
    assert result.reason == "hard invariant"


def test_target_and_session_scope_are_enforced() -> None:
    policy = CapabilityPolicy(
        name="scoped",
        mode=ControlMode.SUPERVISED,
        target_scope=TargetScope(allow=frozenset({"lab-a"}), deny=frozenset({"lab-b"})),
        session_scope=SessionScope(allow=frozenset({"s1"}), deny=frozenset({"s2"})),
    )

    assert (
        policy.decision_for("observe.status", target_id="lab-a", session_id="s1").decision
        == PolicyDecision.ALLOW
    )
    assert (
        policy.decision_for("observe.status", target_id="lab-b", session_id="s1").reason
        == "target outside policy scope"
    )
    assert (
        policy.decision_for("observe.status", target_id="lab-a", session_id="s2").reason
        == "session outside policy scope"
    )


def test_session_scope_cannot_disable_audit_or_emergency_stop() -> None:
    with pytest.raises(ValueError, match="audit logging"):
        SessionScope(require_audit_log=False)

    with pytest.raises(ValueError, match="emergency stop"):
        SessionScope(emergency_stop=False)


def test_load_policy_file_from_schema_shape(tmp_path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "name": "lab supervised",
                "mode": "Supervised",
                "defaults": {
                    "unknown_capability": "deny",
                    "audit": "mandatory",
                    "secrets": "redact_by_default",
                },
                "scope": {
                    "targets": ["lab-a"],
                    "sessions": ["s1"],
                    "allow_real_hardware": False,
                },
                "rules": [
                    {
                        "capability": "media.mount_approved_iso",
                        "decision": "ask_once_per_session",
                        "limits": {"images": ["ubuntu.iso"]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    policy = load_policy_file(policy_path)
    result = policy.decision_for(
        "media.mount_approved_iso",
        target_id="lab-a",
        session_id="s1",
    )

    assert policy.name == "lab supervised"
    assert result.decision == PolicyDecision.ASK_ONCE_PER_SESSION
    assert result.limits["images"] == ["ubuntu.iso"]
    assert DEFAULT_CAPABILITY_REGISTRY.require("media.mount_approved_iso").dangerous


def test_load_policy_file_rejects_unsafe_defaults(tmp_path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "name": "unsafe",
                "mode": "Custom",
                "defaults": {
                    "unknown_capability": "allow",
                    "audit": "mandatory",
                    "secrets": "redact_by_default",
                },
                "rules": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="deny unknown capabilities"):
        load_policy_file(policy_path)
