"""Local operator approval transport.

This module provides a repo-local, dependency-free approval queue for operator
workflows. It persists approval requests and explicit operator decisions to an
operator-supplied path; it does not execute providers, resolve credentials, or
approve anything automatically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from agentickvm.control_plane.approvals import (
    Actor,
    ActorType,
    ApprovalGrant,
    ApprovalGrantScope,
    ApprovalStore,
    CapabilityRef,
)
from agentickvm.control_plane.audit import (
    AuditEventType,
    AuditSink,
    LocalJSONLAuditSink,
    build_audit_event,
    redact_mapping,
)
from agentickvm.control_plane.capabilities import DEFAULT_CAPABILITY_REGISTRY
from agentickvm.control_plane.decisions import PolicyDecision


class LocalApprovalStatus(StrEnum):
    """Local approval queue record status."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CONSUMED = "consumed"


@dataclass(frozen=True)
class LocalApprovalRecord:
    """Persisted local approval queue record."""

    id: str
    status: LocalApprovalStatus
    created_at: datetime
    expires_at: datetime
    session_id: str
    target_id: str
    provider_id: str
    capability_id: str
    params_fingerprint: str
    policy_decision: str
    operator_message: str
    material_risks: tuple[str, ...] = ()
    request: Mapping[str, Any] = field(default_factory=dict)
    scope: ApprovalGrantScope | None = None
    operator_id: str | None = None
    response_id: str | None = None
    reason: str | None = None
    decided_at: datetime | None = None
    consumed_at: datetime | None = None
    redactions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        safe_request, redactions = redact_mapping(dict(self.request))
        object.__setattr__(self, "request", MappingProxyType(dict(safe_request)))
        object.__setattr__(
            self,
            "redactions",
            tuple(self.redactions) + tuple(f"request.{path}" for path in redactions),
        )

    @classmethod
    def from_mcp_result(
        cls,
        result: Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> "LocalApprovalRecord":
        """Build a queue record from an MCP approval_required result."""

        if result.get("status") != "approval_required":
            raise ValueError("result does not require approval")
        data = _mapping(result.get("data", {}), "approval result data")
        approval = _mapping(data.get("approval_request", {}), "approval_request")
        target_scope = _mapping(approval.get("target_scope", {}), "target_scope")
        targets = target_scope.get("targets")
        if not isinstance(targets, list) or not targets or not isinstance(targets[0], str):
            raise ValueError("approval request target scope is missing")
        capability = _mapping(approval.get("capability", {}), "capability")
        created_at = _datetime_from_value(approval.get("created_at")) or now or datetime.now(UTC)
        expires_at = _datetime_from_value(approval.get("expires_at"))
        if expires_at is None:
            raise ValueError("approval request expiry is required")
        params_fingerprint = data.get("params_fingerprint")
        if not isinstance(params_fingerprint, str) or not params_fingerprint:
            raise ValueError("approval params fingerprint is required")
        return cls(
            id=_required_str(approval, "id"),
            status=LocalApprovalStatus.PENDING,
            created_at=created_at,
            expires_at=expires_at,
            session_id=_required_str(approval, "session_id"),
            target_id=targets[0],
            provider_id=_required_str(approval, "provider_id"),
            capability_id=_required_str(capability, "id"),
            params_fingerprint=params_fingerprint,
            policy_decision=_required_str(approval, "policy_decision"),
            operator_message=_redact_text(_required_str(approval, "operator_message")),
            material_risks=tuple(str(item) for item in approval.get("material_risks", ())),
            request={"approval_request": approval, "params_preview": data.get("params_preview", {})},
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> "LocalApprovalRecord":
        """Build a queue record from a JSON-compatible mapping."""

        scope = values.get("scope")
        return cls(
            id=_required_str(values, "id"),
            status=LocalApprovalStatus(_required_str(values, "status")),
            created_at=_required_datetime(values, "created_at"),
            expires_at=_required_datetime(values, "expires_at"),
            session_id=_required_str(values, "session_id"),
            target_id=_required_str(values, "target_id"),
            provider_id=_required_str(values, "provider_id"),
            capability_id=_required_str(values, "capability_id"),
            params_fingerprint=_required_str(values, "params_fingerprint"),
            policy_decision=_required_str(values, "policy_decision"),
            operator_message=_redact_text(_required_str(values, "operator_message")),
            material_risks=tuple(str(item) for item in values.get("material_risks", ())),
            request=_mapping(values.get("request", {}), "request"),
            scope=ApprovalGrantScope(str(scope)) if scope is not None else None,
            operator_id=_optional_str(values.get("operator_id")),
            response_id=_optional_str(values.get("response_id")),
            reason=_redact_text(_optional_str(values.get("reason")) or "") or None,
            decided_at=_datetime_from_value(values.get("decided_at")),
            consumed_at=_datetime_from_value(values.get("consumed_at")),
            redactions=tuple(str(item) for item in values.get("redactions", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe queue record."""

        return _json_safe(
            {
                "id": self.id,
                "status": self.status.value,
                "created_at": self.created_at.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "session_id": self.session_id,
                "target_id": self.target_id,
                "provider_id": self.provider_id,
                "capability_id": self.capability_id,
                "params_fingerprint": self.params_fingerprint,
                "policy_decision": self.policy_decision,
                "operator_message": self.operator_message,
                "material_risks": list(self.material_risks),
                "request": dict(self.request),
                "scope": self.scope.value if self.scope is not None else None,
                "operator_id": self.operator_id,
                "response_id": self.response_id,
                "reason": self.reason,
                "decided_at": self.decided_at.isoformat() if self.decided_at else None,
                "consumed_at": self.consumed_at.isoformat() if self.consumed_at else None,
                "redactions": sorted(set(self.redactions)),
            }
        )

    def to_summary(self) -> dict[str, Any]:
        """Return an operator-readable summary without raw params."""

        return _json_safe(
            {
                "id": self.id,
                "status": self.status.value,
                "session_id": self.session_id,
                "target_id": self.target_id,
                "provider_id": self.provider_id,
                "capability_id": self.capability_id,
                "scope": self.scope.value if self.scope is not None else None,
                "expires_at": self.expires_at.isoformat(),
                "operator_message": self.operator_message,
                "material_risks": list(self.material_risks),
                "redactions": sorted(set(self.redactions)),
            }
        )

    def approved_grant(self, *, now: datetime | None = None) -> ApprovalGrant | None:
        """Return a core approval grant when this record is usable."""

        current = now or datetime.now(UTC)
        if self.status != LocalApprovalStatus.APPROVED:
            return None
        if self.scope is None or self.operator_id is None or self.response_id is None:
            return None
        if current >= self.expires_at:
            return None
        return ApprovalGrant(
            request_id=self.id,
            response_id=self.response_id,
            capability_id=self.capability_id,
            session_id=self.session_id,
            target_id=self.target_id,
            provider_id=self.provider_id,
            params_fingerprint=self.params_fingerprint,
            expires_at=self.expires_at,
            scope=self.scope,
            operator=Actor(type=ActorType.OPERATOR, id=self.operator_id),
        )

    def approve(
        self,
        *,
        operator_id: str,
        scope: ApprovalGrantScope,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> "LocalApprovalRecord":
        """Return an approved copy of this record."""

        current = now or datetime.now(UTC)
        if self.status != LocalApprovalStatus.PENDING:
            raise ValueError(f"approval {self.id} is not pending")
        if current >= self.expires_at:
            return self.expire(operator_id=operator_id, reason="approval expired", now=current)
        response_id = f"local-response-{self.id}-{uuid4().hex}"
        approved = LocalApprovalRecord.from_dict(
            {
                **self.to_dict(),
                "status": LocalApprovalStatus.APPROVED.value,
                "scope": scope.value,
                "operator_id": operator_id,
                "response_id": response_id,
                "reason": _redact_text(reason or "approved"),
                "decided_at": current.isoformat(),
            }
        )
        approved.approved_grant(now=current)
        return approved

    def deny(
        self,
        *,
        operator_id: str,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> "LocalApprovalRecord":
        """Return a denied copy of this record."""

        current = now or datetime.now(UTC)
        if self.status != LocalApprovalStatus.PENDING:
            raise ValueError(f"approval {self.id} is not pending")
        return LocalApprovalRecord.from_dict(
            {
                **self.to_dict(),
                "status": LocalApprovalStatus.DENIED.value,
                "operator_id": operator_id,
                "response_id": f"local-response-{self.id}-{uuid4().hex}",
                "reason": _redact_text(reason or "denied"),
                "decided_at": current.isoformat(),
            }
        )

    def expire(
        self,
        *,
        operator_id: str,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> "LocalApprovalRecord":
        """Return an expired copy of this record."""

        current = now or datetime.now(UTC)
        if self.status not in {LocalApprovalStatus.PENDING, LocalApprovalStatus.APPROVED}:
            raise ValueError(f"approval {self.id} cannot expire from {self.status.value}")
        return LocalApprovalRecord.from_dict(
            {
                **self.to_dict(),
                "status": LocalApprovalStatus.EXPIRED.value,
                "operator_id": operator_id,
                "response_id": self.response_id or f"local-response-{self.id}-{uuid4().hex}",
                "reason": _redact_text(reason or "expired"),
                "decided_at": current.isoformat(),
            }
        )

    def consume(self, *, now: datetime | None = None) -> "LocalApprovalRecord":
        """Return a consumed copy for one-time approvals."""

        if self.status != LocalApprovalStatus.APPROVED:
            raise ValueError(f"approval {self.id} is not approved")
        if self.scope == ApprovalGrantScope.SESSION:
            return self
        current = now or datetime.now(UTC)
        return LocalApprovalRecord.from_dict(
            {
                **self.to_dict(),
                "status": LocalApprovalStatus.CONSUMED.value,
                "consumed_at": current.isoformat(),
            }
        )

    def matches_action(
        self,
        *,
        capability_id: str,
        session_id: str,
        target_id: str,
        provider_id: str,
        params_fingerprint: str,
        now: datetime | None = None,
    ) -> bool:
        """Return whether this record matches an action request."""

        current = now or datetime.now(UTC)
        return (
            self.status == LocalApprovalStatus.APPROVED
            and self.capability_id == capability_id
            and self.session_id == session_id
            and self.target_id == target_id
            and self.provider_id == provider_id
            and self.params_fingerprint == params_fingerprint
            and current < self.expires_at
        )


class LocalApprovalQueue:
    """Path-scoped operator approval queue."""

    def __init__(
        self,
        path: str | Path,
        *,
        audit_path: str | Path | None = None,
        audit_sink: AuditSink | None = None,
        now_factory: Any | None = None,
    ) -> None:
        if audit_path is not None and audit_sink is not None:
            raise ValueError("provide either audit_path or audit_sink, not both")
        self.path = Path(path)
        if self.path.exists() and self.path.is_dir():
            raise ValueError("approval path must be a file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.now_factory = now_factory or (lambda: datetime.now(UTC))
        self.audit_sink: AuditSink | None = audit_sink or (
            LocalJSONLAuditSink(audit_path) if audit_path is not None else None
        )

    def list_records(self) -> tuple[LocalApprovalRecord, ...]:
        """Return all queue records."""

        return tuple(self._load_records().values())

    def get(self, approval_id: str) -> LocalApprovalRecord:
        """Return one queue record or fail closed."""

        records = self._load_records()
        try:
            return records[approval_id]
        except KeyError as exc:
            raise ValueError(f"Unknown approval id: {approval_id}") from exc

    def enqueue_mcp_result(self, result: Mapping[str, Any]) -> LocalApprovalRecord:
        """Persist an approval_required MCP result if it is not already queued."""

        record = LocalApprovalRecord.from_mcp_result(result, now=self.now_factory())
        records = self._load_records()
        existing = records.get(record.id)
        if existing is not None:
            return existing
        records[record.id] = record
        self._save_records(records)
        return record

    def approve(
        self,
        approval_id: str,
        *,
        operator_id: str,
        scope: ApprovalGrantScope = ApprovalGrantScope.ONE_TIME,
        reason: str | None = None,
    ) -> LocalApprovalRecord:
        """Mark a queued approval as granted."""

        records = self._load_records()
        record = self._require_record(records, approval_id)
        updated = record.approve(
            operator_id=operator_id,
            scope=scope,
            reason=reason,
            now=self.now_factory(),
        )
        records[approval_id] = updated
        self._save_records(records)
        self._emit_decision_event(AuditEventType.APPROVAL_GRANTED, updated)
        return updated

    def deny(
        self,
        approval_id: str,
        *,
        operator_id: str,
        reason: str | None = None,
    ) -> LocalApprovalRecord:
        """Mark a queued approval as denied."""

        records = self._load_records()
        record = self._require_record(records, approval_id)
        updated = record.deny(
            operator_id=operator_id,
            reason=reason,
            now=self.now_factory(),
        )
        records[approval_id] = updated
        self._save_records(records)
        self._emit_decision_event(AuditEventType.APPROVAL_DENIED, updated)
        return updated

    def expire(
        self,
        approval_id: str,
        *,
        operator_id: str,
        reason: str | None = None,
    ) -> LocalApprovalRecord:
        """Mark a queued approval as expired."""

        records = self._load_records()
        record = self._require_record(records, approval_id)
        updated = record.expire(
            operator_id=operator_id,
            reason=reason,
            now=self.now_factory(),
        )
        records[approval_id] = updated
        self._save_records(records)
        self._emit_decision_event(AuditEventType.APPROVAL_EXPIRED, updated)
        return updated

    def to_approval_store(self) -> ApprovalStore:
        """Return a core approval store populated with usable grants."""

        store = ApprovalStore()
        for record in self.list_records():
            grant = record.approved_grant(now=self.now_factory())
            if grant is not None:
                store.add_action_grant(grant)
        return store

    def mark_matching_consumed(
        self,
        *,
        capability_id: str,
        session_id: str,
        target_id: str,
        provider_id: str,
        params_fingerprint: str,
    ) -> LocalApprovalRecord | None:
        """Mark a matching one-time approval consumed after ControlPlane use."""

        records = self._load_records()
        for approval_id, record in records.items():
            if record.matches_action(
                capability_id=capability_id,
                session_id=session_id,
                target_id=target_id,
                provider_id=provider_id,
                params_fingerprint=params_fingerprint,
                now=self.now_factory(),
            ):
                if record.scope == ApprovalGrantScope.SESSION:
                    return None
                updated = record.consume(now=self.now_factory())
                records[approval_id] = updated
                self._save_records(records)
                return updated
        return None

    def _load_records(self) -> dict[str, LocalApprovalRecord]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("approval queue must contain an object")
        raw_records = payload.get("approvals", [])
        if not isinstance(raw_records, list):
            raise ValueError("approval queue approvals must be a list")
        records: dict[str, LocalApprovalRecord] = {}
        for item in raw_records:
            if not isinstance(item, Mapping):
                raise ValueError("approval queue records must be objects")
            record = LocalApprovalRecord.from_dict(item)
            records[record.id] = record
        return records

    def _save_records(self, records: Mapping[str, LocalApprovalRecord]) -> None:
        payload = {
            "version": "0.1",
            "approvals": [
                record.to_dict()
                for record in sorted(records.values(), key=lambda item: item.created_at)
            ],
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _require_record(
        self,
        records: Mapping[str, LocalApprovalRecord],
        approval_id: str,
    ) -> LocalApprovalRecord:
        try:
            return records[approval_id]
        except KeyError as exc:
            raise ValueError(f"Unknown approval id: {approval_id}") from exc

    def _emit_decision_event(
        self,
        event_type: AuditEventType,
        record: LocalApprovalRecord,
    ) -> None:
        if self.audit_sink is None:
            return
        capability = DEFAULT_CAPABILITY_REGISTRY.require(record.capability_id)
        event = build_audit_event(
            event_type=event_type,
            correlation_id=f"approval-transport:{record.id}",
            session_id=record.session_id,
            target_id=record.target_id,
            actor=Actor(
                type=ActorType.OPERATOR,
                id=record.operator_id or "unknown-operator",
            ),
            capability=CapabilityRef.from_capability(capability),
            policy_decision=PolicyDecision(record.policy_decision),
            request={"approval_request": dict(record.request)},
            result={
                "status": record.status.value,
                "scope": record.scope.value if record.scope else None,
                "reason": record.reason,
            },
            material_risks=record.material_risks,
        )
        self.audit_sink.emit(event)


def _required_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"approval {key} is required")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("approval optional string fields must be strings")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _required_datetime(values: Mapping[str, Any], key: str) -> datetime:
    value = _datetime_from_value(values.get(key))
    if value is None:
        raise ValueError(f"approval {key} is required")
    return value


def _datetime_from_value(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        raise ValueError("approval datetime fields must be ISO datetime strings")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _redact_text(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.lower()
    if any(
        token in lowered
        for token in ("password", "secret", "token", "api_key", "private_key", "bearer")
    ):
        return "[REDACTED]"
    return value


__all__ = [
    "LocalApprovalQueue",
    "LocalApprovalRecord",
    "LocalApprovalStatus",
]
