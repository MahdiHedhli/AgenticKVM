"""Approval models for gated control-plane decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping
from uuid import uuid4

from agentickvm.control_plane.capabilities import Capability
from agentickvm.control_plane.decisions import PolicyDecision
from agentickvm.control_plane.policy import PolicyDecisionResult


class ActorType(StrEnum):
    """Known actor types in approval and audit models."""

    AGENT = "agent"
    OPERATOR = "operator"
    SERVICE = "service"
    PROVIDER = "provider"
    TEST = "test"


class ApprovalOutcome(StrEnum):
    """Operator approval response outcome."""

    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalGrantScope(StrEnum):
    """Reusable scope of an approval grant."""

    ONE_TIME = "one_time"
    SESSION = "session"


APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES = frozenset(
    {
        "session.modify_policy",
        "session.disable_audit",
        "session.disable_emergency_stop",
        "secrets.raw_reveal",
    }
)


@dataclass(frozen=True)
class Actor:
    """Requester or operator identity."""

    type: ActorType
    id: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Actor id is required")

    def to_dict(self) -> dict[str, str]:
        """Return a schema-compatible dictionary."""

        return {"type": self.type.value, "id": self.id}


@dataclass(frozen=True)
class CapabilityRef:
    """Small schema-compatible capability reference."""

    id: str
    family: str
    action: str

    @classmethod
    def from_capability(cls, capability: Capability) -> "CapabilityRef":
        """Build a reference from a registry capability."""

        return cls(
            id=capability.id,
            family=capability.family,
            action=capability.action,
        )

    def to_dict(self) -> dict[str, str]:
        """Return a schema-compatible dictionary."""

        return {
            "id": self.id,
            "family": self.family,
            "action": self.action,
        }


@dataclass(frozen=True)
class ApprovalRequest:
    """Explainable approval request for an operator."""

    id: str
    created_at: datetime
    expires_at: datetime
    session_id: str
    requester: Actor
    capability: CapabilityRef
    target_ids: tuple[str, ...]
    policy_decision: PolicyDecision
    operator_message: str
    material_risks: tuple[str, ...]
    proposed_audit_event_id: str
    provider_id: str | None = None
    limits: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.policy_decision not in {
            PolicyDecision.ASK_EACH_TIME,
            PolicyDecision.ASK_ONCE_PER_SESSION,
        }:
            raise ValueError("Approval requests require an ask policy decision")
        if not self.target_ids:
            raise ValueError("Approval request requires target scope")
        if not self.material_risks:
            raise ValueError("Approval request requires material risks")
        if self.expires_at <= self.created_at:
            raise ValueError("Approval request expiry must be after creation")
        object.__setattr__(self, "limits", MappingProxyType(dict(self.limits)))

    def to_dict(self) -> dict[str, Any]:
        """Return a schema-compatible dictionary."""

        data: dict[str, Any] = {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "session_id": self.session_id,
            "requester": self.requester.to_dict(),
            "capability": self.capability.to_dict(),
            "target_scope": {
                "targets": list(self.target_ids),
                "allow_real_hardware": False,
            },
            "policy_decision": self.policy_decision.value,
            "operator_message": self.operator_message,
            "material_risks": list(self.material_risks),
            "proposed_audit_event_id": self.proposed_audit_event_id,
        }
        if self.limits:
            data["limits"] = dict(self.limits)
        if self.provider_id is not None:
            data["provider_id"] = self.provider_id
        return data


@dataclass(frozen=True)
class ApprovalResponse:
    """Operator response to an approval request."""

    id: str
    request_id: str
    outcome: ApprovalOutcome
    operator: Actor
    decided_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.operator.type != ActorType.OPERATOR:
            raise ValueError("Approval responses require an operator actor")


@dataclass(frozen=True)
class SessionApprovalGrant:
    """Reusable approval grant with exact session and target scope."""

    request_id: str
    capability_id: str
    session_id: str
    target_ids: frozenset[str]
    expires_at: datetime
    limits: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "limits", MappingProxyType(dict(self.limits)))

    def matches(
        self,
        *,
        capability_id: str,
        session_id: str,
        target_id: str,
        now: datetime,
    ) -> bool:
        """Return whether this grant can be reused for a request."""

        return (
            capability_id == self.capability_id
            and session_id == self.session_id
            and target_id in self.target_ids
            and now < self.expires_at
        )


@dataclass(frozen=True)
class ApprovalGrant:
    """Approval grant bound to an exact provider, target, capability, and params."""

    request_id: str
    response_id: str
    capability_id: str
    session_id: str
    target_id: str
    provider_id: str
    params_fingerprint: str
    expires_at: datetime
    scope: ApprovalGrantScope
    operator: Actor

    def __post_init__(self) -> None:
        if self.capability_id in APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES:
            raise ValueError(f"Capability cannot be approval-resumed: {self.capability_id}")
        if self.operator.type != ActorType.OPERATOR:
            raise ValueError("Approval grants require an operator actor")

    @property
    def reusable(self) -> bool:
        """Return whether this grant is reusable within the session."""

        return self.scope == ApprovalGrantScope.SESSION

    def matches(
        self,
        *,
        capability_id: str,
        session_id: str,
        target_id: str,
        provider_id: str,
        params_fingerprint: str,
        now: datetime,
    ) -> bool:
        """Return whether this grant authorizes the exact requested action."""

        return (
            capability_id == self.capability_id
            and session_id == self.session_id
            and target_id == self.target_id
            and provider_id == self.provider_id
            and params_fingerprint == self.params_fingerprint
            and now < self.expires_at
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a schema-compatible dictionary."""

        return {
            "request_id": self.request_id,
            "response_id": self.response_id,
            "capability_id": self.capability_id,
            "session_id": self.session_id,
            "target_id": self.target_id,
            "provider_id": self.provider_id,
            "params_fingerprint": self.params_fingerprint,
            "expires_at": self.expires_at.isoformat(),
            "scope": self.scope.value,
            "operator": self.operator.to_dict(),
        }


class ApprovalStore:
    """In-memory approval grant store for tests and bootstrap development."""

    def __init__(self) -> None:
        self._grants: list[SessionApprovalGrant] = []
        self._action_grants: list[ApprovalGrant] = []
        self._consumed_response_ids: set[str] = set()

    def add(self, grant: SessionApprovalGrant) -> None:
        """Store a reusable approval grant."""

        self._grants.append(grant)

    def add_action_grant(self, grant: ApprovalGrant) -> None:
        """Store a provider-bound action approval grant."""

        self._action_grants.append(grant)

    def find(
        self,
        *,
        capability_id: str,
        session_id: str,
        target_id: str,
        now: datetime,
    ) -> SessionApprovalGrant | None:
        """Return a matching, unexpired grant."""

        for grant in self._grants:
            if grant.matches(
                capability_id=capability_id,
                session_id=session_id,
                target_id=target_id,
                now=now,
            ):
                return grant
        return None

    def grant_from_response(
        self,
        *,
        request: ApprovalRequest,
        response: ApprovalResponse,
        provider_id: str,
        parameters: Mapping[str, Any],
        scope: ApprovalGrantScope = ApprovalGrantScope.ONE_TIME,
    ) -> ApprovalGrant:
        """Create and store an exact action grant from an approval response."""

        if response.request_id != request.id:
            raise ValueError("Approval response does not match request")
        if response.outcome != ApprovalOutcome.GRANTED:
            raise ValueError("Only granted approval responses create grants")
        if request.capability.id in APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES:
            raise ValueError(f"Capability cannot be approval-resumed: {request.capability.id}")
        if provider_id != (request.provider_id or provider_id):
            raise ValueError("Approval provider does not match request provider")

        grant = ApprovalGrant(
            request_id=request.id,
            response_id=response.id,
            capability_id=request.capability.id,
            session_id=request.session_id,
            target_id=request.target_ids[0],
            provider_id=provider_id,
            params_fingerprint=fingerprint_parameters(parameters),
            expires_at=request.expires_at,
            scope=scope,
            operator=response.operator,
        )
        self.add_action_grant(grant)
        return grant

    def find_action_grant(
        self,
        *,
        capability_id: str,
        session_id: str,
        target_id: str,
        provider_id: str,
        params_fingerprint: str,
        now: datetime,
    ) -> ApprovalGrant | None:
        """Return a matching, unexpired, unconsumed action grant."""

        for grant in self._action_grants:
            if (
                not grant.reusable
                and grant.response_id in self._consumed_response_ids
            ):
                continue
            if grant.matches(
                capability_id=capability_id,
                session_id=session_id,
                target_id=target_id,
                provider_id=provider_id,
                params_fingerprint=params_fingerprint,
                now=now,
            ):
                return grant
        return None

    def consume(self, grant: ApprovalGrant) -> None:
        """Mark a one-time grant as consumed."""

        if not grant.reusable:
            self._consumed_response_ids.add(grant.response_id)


class EmergencyStopActive(RuntimeError):
    """Raised when emergency stop prevents execution."""


@dataclass(frozen=True)
class EmergencyStopState:
    """Emergency stop state for a session or runtime."""

    active: bool = False
    reason: str | None = None
    activated_by: Actor | None = None

    def require_clear(self) -> None:
        """Raise when emergency stop is active."""

        if self.active:
            reason = f": {self.reason}" if self.reason else ""
            raise EmergencyStopActive(f"Emergency stop is active{reason}")


def build_approval_request(
    *,
    decision_result: PolicyDecisionResult,
    capability: Capability,
    session_id: str,
    requester: Actor,
    target_ids: tuple[str, ...],
    intended_effect: str,
    ttl: timedelta = timedelta(minutes=15),
    now: datetime | None = None,
    id_factory: Callable[[], str] | None = None,
    provider_id: str | None = None,
) -> ApprovalRequest:
    """Build an explainable approval request from a policy decision."""

    if not decision_result.requires_approval:
        raise ValueError("Policy decision does not require approval")

    created_at = now or datetime.now(UTC)
    new_id = id_factory or (lambda: uuid4().hex)
    material_risks = decision_result.material_risks or ("operator approval required",)
    operator_message = (
        f"{requester.id} requests {capability.id} for targets "
        f"{', '.join(target_ids)}. Intended effect: {intended_effect}. "
        f"Policy decision: {decision_result.decision.value}."
    )

    return ApprovalRequest(
        id=new_id(),
        created_at=created_at,
        expires_at=created_at + ttl,
        session_id=session_id,
        requester=requester,
        capability=CapabilityRef.from_capability(capability),
        target_ids=target_ids,
        policy_decision=decision_result.decision,
        operator_message=operator_message,
        material_risks=material_risks,
        proposed_audit_event_id=new_id(),
        provider_id=provider_id,
        limits=decision_result.limits,
    )


def fingerprint_parameters(parameters: Mapping[str, Any]) -> str:
    """Return a stable action fingerprint for provider parameters."""

    encoded = json.dumps(
        _canonical_json_value(parameters),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical_json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_json_value(child) for child in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical_json_value(child) for child in value)
    return value
