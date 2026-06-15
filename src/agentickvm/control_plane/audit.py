"""Structured audit events for the control plane."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol
from uuid import uuid4

from agentickvm.control_plane.approvals import Actor, CapabilityRef
from agentickvm.control_plane.decisions import PolicyDecision
from agentickvm.redaction import redact_mapping as redact_agentickvm_mapping


class AuditEventType(StrEnum):
    """Audit event types from the audit event contract."""

    REQUEST_RECEIVED = "request_received"
    CAPABILITY_RESOLVED = "capability_resolved"
    CAPABILITY_UNKNOWN_DENIED = "capability_unknown_denied"
    POLICY_DECISION = "policy_decision"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_EXPIRED = "approval_expired"
    APPROVAL_REUSED = "approval_reused"
    APPROVAL_VERIFIED = "approval_verified"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_CONSUMED = "approval_consumed"
    PROVIDER_EXECUTION_STARTED = "provider_execution_started"
    PROVIDER_EXECUTION_COMPLETED = "provider_execution_completed"
    PROVIDER_EXECUTION_FAILED = "provider_execution_failed"
    RESULT_RETURNED = "result_returned"


@dataclass(frozen=True)
class ProviderRef:
    """Provider metadata for audit events."""

    id: str
    kind: str
    is_real_hardware: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a schema-compatible dictionary."""

        return {
            "id": self.id,
            "kind": self.kind,
            "is_real_hardware": self.is_real_hardware,
        }


@dataclass(frozen=True)
class AuditEvent:
    """Structured audit event."""

    id: str
    timestamp: datetime
    event_type: AuditEventType
    correlation_id: str
    session_id: str
    actor: Actor
    capability: CapabilityRef
    policy_decision: PolicyDecision
    redactions: tuple[str, ...]
    target_id: str | None = None
    approval: Mapping[str, Any] | None = None
    provider: ProviderRef | None = None
    request: Mapping[str, Any] | None = None
    result: Mapping[str, Any] | None = None
    material_risks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.provider is not None and self.provider.is_real_hardware:
            provider_id = self.provider.id
            if self.event_type == AuditEventType.REQUEST_RECEIVED:
                raise ValueError(f"Request event cannot mark real provider {provider_id}")

    def to_dict(self) -> dict[str, Any]:
        """Return a schema-compatible dictionary."""

        data: dict[str, Any] = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "actor": self.actor.to_dict(),
            "capability": self.capability.to_dict(),
            "policy_decision": self.policy_decision.value,
            "redactions": list(self.redactions),
        }
        if self.target_id is not None:
            data["target_id"] = self.target_id
        if self.approval is not None:
            data["approval"] = dict(self.approval)
        if self.provider is not None:
            data["provider"] = self.provider.to_dict()
        if self.request is not None:
            data["request"] = dict(self.request)
        if self.result is not None:
            data["result"] = dict(self.result)
        if self.material_risks:
            data["material_risks"] = list(self.material_risks)
        return data


class AuditSink(Protocol):
    """Destination for audit events."""

    def emit(self, event: AuditEvent) -> None:
        """Record an audit event."""


class InMemoryAuditSink:
    """Audit sink for tests and bootstrap flows."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        """Record an event in memory."""

        self.events.append(event)


class LocalJSONLAuditSink:
    """Local JSONL audit sink with a tamper-evident hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.exists() and self.path.is_dir():
            raise ValueError("Audit path must be a file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._previous_hash = _last_event_hash(self.path)

    def emit(self, event: AuditEvent) -> None:
        """Append a redacted audit event to JSONL."""

        event_payload = _redacted_event_payload(event)
        unsigned_record = {
            "previous_hash": self._previous_hash,
            "event": event_payload,
        }
        event_hash = _hash_mapping(unsigned_record)
        record = {
            **unsigned_record,
            "event_hash": event_hash,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
        self._previous_hash = event_hash


def verify_audit_chain(path: str | Path) -> bool:
    """Return whether a JSONL audit hash chain verifies."""

    audit_path = Path(path)
    previous_hash: str | None = None
    if not audit_path.exists():
        return True

    with audit_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            expected_previous = record.get("previous_hash")
            if expected_previous != previous_hash:
                return False
            expected_hash = record.get("event_hash")
            unsigned_record = {
                "previous_hash": expected_previous,
                "event": record.get("event"),
            }
            if expected_hash != _hash_mapping(unsigned_record):
                return False
            previous_hash = expected_hash
    return True


def redact_mapping(values: Mapping[str, Any]) -> tuple[Mapping[str, Any], tuple[str, ...]]:
    """Return a redacted copy of a mapping and the redacted paths."""

    return redact_agentickvm_mapping(values)


def build_audit_event(
    *,
    event_type: AuditEventType,
    correlation_id: str,
    session_id: str,
    actor: Actor,
    capability: CapabilityRef,
    policy_decision: PolicyDecision,
    target_id: str | None = None,
    request: Mapping[str, Any] | None = None,
    result: Mapping[str, Any] | None = None,
    material_risks: tuple[str, ...] = (),
) -> AuditEvent:
    """Build an audit event with default timestamp and redaction."""

    redacted_request: Mapping[str, Any] | None = None
    redacted_result: Mapping[str, Any] | None = None
    redactions: list[str] = []

    if request is not None:
        redacted_request, request_redactions = redact_mapping(request)
        redactions.extend(f"request.{item}" for item in request_redactions)
    if result is not None:
        redacted_result, result_redactions = redact_mapping(result)
        redactions.extend(f"result.{item}" for item in result_redactions)

    return AuditEvent(
        id=uuid4().hex,
        timestamp=datetime.now(UTC),
        event_type=event_type,
        correlation_id=correlation_id,
        session_id=session_id,
        actor=actor,
        capability=capability,
        policy_decision=policy_decision,
        target_id=target_id,
        request=redacted_request,
        result=redacted_result,
        redactions=tuple(redactions),
        material_risks=material_risks,
    )


def _redacted_event_payload(event: AuditEvent) -> dict[str, Any]:
    payload = event.to_dict()
    redactions = set(payload.get("redactions", []))
    for section in ("request", "result", "approval"):
        section_value = payload.get(section)
        if isinstance(section_value, Mapping):
            redacted, paths = redact_mapping(section_value)
            payload[section] = dict(redacted)
            redactions.update(f"{section}.{path}" for path in paths)
    payload["redactions"] = sorted(redactions)
    return payload


def _hash_mapping(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _last_event_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    last_hash: str | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_hash = json.loads(line).get("event_hash")
    return last_hash
