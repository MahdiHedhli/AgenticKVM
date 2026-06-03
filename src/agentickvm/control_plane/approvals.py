"""Approval models for gated control-plane decisions."""

from __future__ import annotations

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


class ApprovalStore:
    """In-memory approval grant store for tests and bootstrap development."""

    def __init__(self) -> None:
        self._grants: list[SessionApprovalGrant] = []

    def add(self, grant: SessionApprovalGrant) -> None:
        """Store a reusable approval grant."""

        self._grants.append(grant)

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
        limits=decision_result.limits,
    )
