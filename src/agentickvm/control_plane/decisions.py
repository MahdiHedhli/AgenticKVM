"""Control-plane vocabulary for modes and policy decisions."""

from __future__ import annotations

from enum import StrEnum


class ControlMode(StrEnum):
    """Operator-visible control modes."""

    OBSERVE = "Observe"
    ASSISTED = "Assisted"
    SUPERVISED = "Supervised"
    FULL_CONTROL = "Full Control"
    CUSTOM = "Custom"


class PolicyDecision(StrEnum):
    """Internal policy decisions."""

    DENY = "deny"
    ASK_EACH_TIME = "ask_each_time"
    ASK_ONCE_PER_SESSION = "ask_once_per_session"
    ALLOW = "allow"
    ALLOW_WITH_LIMITS = "allow_with_limits"


def normalize_control_mode(value: ControlMode | str) -> ControlMode:
    """Return a control mode from display or lower-case policy text."""

    if isinstance(value, ControlMode):
        return value

    normalized = value.strip().replace("_", " ").replace("-", " ").lower()
    aliases = {
        "observe": ControlMode.OBSERVE,
        "assisted": ControlMode.ASSISTED,
        "supervised": ControlMode.SUPERVISED,
        "full control": ControlMode.FULL_CONTROL,
        "fullcontrol": ControlMode.FULL_CONTROL,
        "custom": ControlMode.CUSTOM,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown control mode: {value}") from exc


def normalize_policy_decision(value: PolicyDecision | str) -> PolicyDecision:
    """Return a policy decision from policy text."""

    if isinstance(value, PolicyDecision):
        return value
    try:
        return PolicyDecision(value)
    except ValueError as exc:
        raise ValueError(f"Unknown policy decision: {value}") from exc
