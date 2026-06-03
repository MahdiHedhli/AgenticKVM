"""Initial policy decision engine.

The policy engine returns decisions only. It does not approve requests, call
providers, or write audit events.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.control_plane.capabilities import (
    Capability,
    CapabilityRegistry,
    DEFAULT_CAPABILITY_REGISTRY,
)
from agentickvm.control_plane.decisions import (
    ControlMode,
    PolicyDecision,
    normalize_control_mode,
    normalize_policy_decision,
)

HARD_DENY_CAPABILITIES = frozenset(
    {
        "session.modify_policy",
        "session.disable_audit",
        "session.disable_emergency_stop",
    }
)


@dataclass(frozen=True)
class TargetScope:
    """Target allow/deny scope for a policy."""

    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()
    allow_real_hardware: bool = False

    def allows(self, target_id: str | None) -> bool:
        """Return whether a target is inside scope."""

        if target_id is None:
            return not self.allow and not self.deny
        if target_id in self.deny:
            return False
        return not self.allow or target_id in self.allow


@dataclass(frozen=True)
class SessionScope:
    """Session constraints for policy evaluation."""

    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()
    require_audit_log: bool = True
    emergency_stop: bool = True

    def __post_init__(self) -> None:
        if not self.require_audit_log:
            raise ValueError("Policy cannot disable audit logging")
        if not self.emergency_stop:
            raise ValueError("Policy cannot disable emergency stop")

    def allows(self, session_id: str | None) -> bool:
        """Return whether a session is inside scope."""

        if session_id is None:
            return not self.allow and not self.deny
        if session_id in self.deny:
            return False
        return not self.allow or session_id in self.allow


@dataclass(frozen=True)
class PolicyRule:
    """Explicit policy rule for a capability."""

    decision: PolicyDecision
    limits: Mapping[str, Any] = field(default_factory=dict)
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "limits", MappingProxyType(dict(self.limits)))


@dataclass(frozen=True)
class PolicyDecisionResult:
    """Result of evaluating one capability request."""

    capability_id: str
    decision: PolicyDecision
    reason: str
    matched_rule: str | None = None
    limits: Mapping[str, Any] = field(default_factory=dict)
    material_risks: tuple[str, ...] = ()

    @property
    def requires_approval(self) -> bool:
        """Return whether the decision requires operator approval."""

        return self.decision in {
            PolicyDecision.ASK_EACH_TIME,
            PolicyDecision.ASK_ONCE_PER_SESSION,
        }


@dataclass(frozen=True)
class CapabilityPolicy:
    """Mode, scope, and explicit rules for policy evaluation."""

    name: str
    mode: ControlMode
    target_scope: TargetScope = field(default_factory=TargetScope)
    session_scope: SessionScope = field(default_factory=SessionScope)
    rules: Mapping[str, PolicyRule] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", normalize_control_mode(self.mode))
        object.__setattr__(self, "rules", MappingProxyType(dict(self.rules)))

    def decision_for(
        self,
        capability_id: str,
        *,
        target_id: str | None = None,
        session_id: str | None = None,
        credential_id: str | None = None,
        registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
    ) -> PolicyDecisionResult:
        """Return the effective decision for a capability request."""

        capability = registry.get(capability_id)
        if capability is None:
            return PolicyDecisionResult(
                capability_id=capability_id,
                decision=PolicyDecision.DENY,
                reason="unknown capability",
            )

        if capability_id in HARD_DENY_CAPABILITIES:
            return PolicyDecisionResult(
                capability_id=capability_id,
                decision=PolicyDecision.DENY,
                reason="hard invariant",
                material_risks=_risks_for(capability),
            )

        if "target" in capability.required_scope and target_id is None:
            return PolicyDecisionResult(
                capability_id=capability_id,
                decision=PolicyDecision.DENY,
                reason="missing required target scope",
                material_risks=_risks_for(capability),
            )

        if "session" in capability.required_scope and session_id is None:
            return PolicyDecisionResult(
                capability_id=capability_id,
                decision=PolicyDecision.DENY,
                reason="missing required session scope",
                material_risks=_risks_for(capability),
            )

        if "credential" in capability.required_scope and credential_id is None:
            return PolicyDecisionResult(
                capability_id=capability_id,
                decision=PolicyDecision.DENY,
                reason="missing required credential scope",
                material_risks=_risks_for(capability),
            )

        if not self.target_scope.allows(target_id):
            return PolicyDecisionResult(
                capability_id=capability_id,
                decision=PolicyDecision.DENY,
                reason="target outside policy scope",
                material_risks=_risks_for(capability),
            )

        if not self.session_scope.allows(session_id):
            return PolicyDecisionResult(
                capability_id=capability_id,
                decision=PolicyDecision.DENY,
                reason="session outside policy scope",
                material_risks=_risks_for(capability),
            )

        rule = self.rules.get(capability_id)
        if rule is not None:
            return PolicyDecisionResult(
                capability_id=capability_id,
                decision=rule.decision,
                reason=rule.reason or "explicit policy rule",
                matched_rule=capability_id,
                limits=rule.limits,
                material_risks=_risks_for(capability),
            )

        return PolicyDecisionResult(
            capability_id=capability_id,
            decision=default_decision_for_mode(self.mode, capability),
            reason=f"default {self.mode.value} mode decision",
            material_risks=_risks_for(capability),
        )


def default_decision_for_mode(
    mode: ControlMode | str,
    capability: Capability,
) -> PolicyDecision:
    """Return the built-in mode decision for a known capability."""

    normalized_mode = normalize_control_mode(mode)

    if capability.id in HARD_DENY_CAPABILITIES:
        return PolicyDecision.DENY

    if normalized_mode == ControlMode.CUSTOM:
        return PolicyDecision.DENY

    if normalized_mode == ControlMode.OBSERVE:
        if capability.family in {"observe", "session"} and not capability.dangerous:
            return PolicyDecision.ALLOW
        return PolicyDecision.DENY

    if normalized_mode == ControlMode.ASSISTED:
        if capability.family in {"observe", "session"} and not capability.dangerous:
            return PolicyDecision.ALLOW
        if capability.destructive or capability.risk == "critical":
            return PolicyDecision.DENY
        return PolicyDecision.ASK_EACH_TIME

    if normalized_mode == ControlMode.SUPERVISED:
        if capability.family in {"observe", "session"} and not capability.dangerous:
            return PolicyDecision.ALLOW
        if capability.id in {"media.mount_approved_iso", "secrets.inject_reference"}:
            return PolicyDecision.ASK_ONCE_PER_SESSION
        if capability.dangerous:
            return PolicyDecision.ASK_EACH_TIME
        return PolicyDecision.ALLOW_WITH_LIMITS

    if normalized_mode == ControlMode.FULL_CONTROL:
        if capability.id == "secrets.raw_reveal":
            return PolicyDecision.ASK_EACH_TIME
        return PolicyDecision.ALLOW

    return PolicyDecision.DENY


def mode_preset(mode: ControlMode | str, *, name: str | None = None) -> CapabilityPolicy:
    """Return a built-in policy preset."""

    normalized_mode = normalize_control_mode(mode)
    return CapabilityPolicy(
        name=name or f"default {normalized_mode.value}",
        mode=normalized_mode,
    )


def load_policy_file(
    path: str | Path,
    *,
    registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
) -> CapabilityPolicy:
    """Load a JSON policy document aligned with the policy schema.

    YAML support is intentionally deferred until policy loading requirements are
    stable and dependency choices are explicit.
    """

    policy_path = Path(path)
    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Policy file must contain a JSON object")

    defaults = raw.get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError("Policy file must contain defaults")
    if defaults.get("unknown_capability") != PolicyDecision.DENY.value:
        raise ValueError("Policy defaults must deny unknown capabilities")
    if defaults.get("audit") != "mandatory":
        raise ValueError("Policy defaults must require mandatory audit")
    if defaults.get("secrets") != "redact_by_default":
        raise ValueError("Policy defaults must redact secrets by default")

    scope = raw.get("scope") if isinstance(raw.get("scope"), dict) else {}
    target_scope = TargetScope(
        allow=frozenset(scope.get("targets", [])),
        allow_real_hardware=bool(scope.get("allow_real_hardware", False)),
    )
    session_scope = SessionScope(
        allow=frozenset(scope.get("sessions", [])),
    )

    rules: dict[str, PolicyRule] = {}
    for item in raw.get("rules", []):
        if not isinstance(item, dict):
            raise ValueError("Policy rules must be objects")
        capability_id = item.get("capability")
        if not isinstance(capability_id, str):
            raise ValueError("Policy rule capability must be a string")
        if registry.get(capability_id) is None:
            raise ValueError(f"Unknown capability in policy: {capability_id}")
        rules[capability_id] = PolicyRule(
            decision=normalize_policy_decision(item.get("decision", "")),
            limits=item.get("limits", {}),
            reason=item.get("notes"),
        )

    return CapabilityPolicy(
        name=str(raw.get("name", "unnamed policy")),
        mode=normalize_control_mode(str(raw["mode"])),
        target_scope=target_scope,
        session_scope=session_scope,
        rules=rules,
    )


def _risks_for(capability: Capability) -> tuple[str, ...]:
    risks: list[str] = []
    if capability.dangerous:
        risks.append("dangerous action")
    if capability.destructive:
        risks.append("destructive action")
    if capability.id == "secrets.raw_reveal":
        risks.append("raw secret reveal")
    return tuple(risks)
