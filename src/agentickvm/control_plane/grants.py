"""Signed approval grant models.

These models define the payload shape used by Approval Broker v1. Signing and
verification live in a later broker layer; this module keeps canonical
serialization stable and JSON-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.control_plane.fingerprints import canonical_json


GRANT_PAYLOAD_VERSION = "approval-grant-v1"


class GrantDecision(StrEnum):
    """Operator decision represented by the broker."""

    GRANT = "grant"
    DENY = "deny"


class GrantScope(StrEnum):
    """Grant reuse scope."""

    ONE_TIME = "one_time"
    SESSION = "session"


class ApprovalChannel(StrEnum):
    """Approval channel family."""

    HOST_NATIVE = "host_native"
    OUT_OF_BAND = "out_of_band"
    WATCH_TUI = "watch_tui"
    CONVERSATIONAL = "conversational"
    TEST = "test"


class GrantVerificationStatus(StrEnum):
    """Signed grant verification outcome."""

    VALID = "valid"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    MALFORMED = "malformed"
    UNSIGNED = "unsigned"


@dataclass(frozen=True)
class ApprovalRiskSummary:
    """Operator-readable risk summary for an approval request."""

    risk_family: str
    summary: str
    material_risks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.risk_family:
            raise ValueError("risk family is required")
        if not self.summary:
            raise ValueError("risk summary is required")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary."""

        return {
            "risk_family": self.risk_family,
            "summary": self.summary,
            "material_risks": list(self.material_risks),
        }


@dataclass(frozen=True)
class ApprovalShortCode:
    """Short human code used to correlate out-of-band approval."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("short code is required")
        if not self.value.replace("-", "").isalnum():
            raise ValueError("short code must be alphanumeric or hyphenated")

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-safe dictionary."""

        return {"value": self.value}


@dataclass(frozen=True)
class GrantPayload:
    """Canonical signed approval grant payload."""

    grant_id: str
    request_id: str
    session_id: str
    target: str
    provider: str
    capability: str
    params_fingerprint: str
    risk_family: str
    channel: ApprovalChannel
    expires_at: datetime
    one_time: bool = True
    consumed_at: datetime | None = None
    policy_constraints: Mapping[str, Any] = field(default_factory=dict)
    signer_key_id: str = ""
    payload_version: str = GRANT_PAYLOAD_VERSION

    def __post_init__(self) -> None:
        required = {
            "grant_id": self.grant_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "target": self.target,
            "provider": self.provider,
            "capability": self.capability,
            "params_fingerprint": self.params_fingerprint,
            "risk_family": self.risk_family,
            "signer_key_id": self.signer_key_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"grant payload missing required fields: {', '.join(missing)}")
        if self.expires_at.tzinfo is None:
            raise ValueError("grant expiry must be timezone-aware")
        object.__setattr__(self, "policy_constraints", MappingProxyType(dict(self.policy_constraints)))

    @property
    def reusable(self) -> bool:
        """Return whether this grant can be reused within its exact binding."""

        return not self.one_time

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe signed payload fields."""

        return {
            "payload_version": self.payload_version,
            "grant_id": self.grant_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "target": self.target,
            "provider": self.provider,
            "capability": self.capability,
            "params_fingerprint": self.params_fingerprint,
            "risk_family": self.risk_family,
            "channel": self.channel.value,
            "expires_at": self.expires_at.astimezone(UTC).isoformat(),
            "one_time": self.one_time,
            "consumed_at": self.consumed_at.astimezone(UTC).isoformat()
            if self.consumed_at
            else None,
            "policy_constraints": dict(self.policy_constraints),
            "signer_key_id": self.signer_key_id,
        }

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> "GrantPayload":
        """Build a grant payload from a JSON-safe mapping."""

        return cls(
            payload_version=_required_str(values, "payload_version"),
            grant_id=_required_str(values, "grant_id"),
            request_id=_required_str(values, "request_id"),
            session_id=_required_str(values, "session_id"),
            target=_required_str(values, "target"),
            provider=_required_str(values, "provider"),
            capability=_required_str(values, "capability"),
            params_fingerprint=_required_str(values, "params_fingerprint"),
            risk_family=_required_str(values, "risk_family"),
            channel=ApprovalChannel(_required_str(values, "channel")),
            expires_at=_parse_datetime(_required_str(values, "expires_at")),
            one_time=bool(values.get("one_time", True)),
            consumed_at=_parse_optional_datetime(values.get("consumed_at")),
            policy_constraints=_mapping(values.get("policy_constraints", {})),
            signer_key_id=_required_str(values, "signer_key_id"),
        )

    def canonical_payload(self) -> str:
        """Return the canonical string that must be signed."""

        return canonical_json(self.to_dict())

    def with_consumed_at(self, consumed_at: datetime) -> "GrantPayload":
        """Return a copy marked consumed."""

        return GrantPayload(
            grant_id=self.grant_id,
            request_id=self.request_id,
            session_id=self.session_id,
            target=self.target,
            provider=self.provider,
            capability=self.capability,
            params_fingerprint=self.params_fingerprint,
            risk_family=self.risk_family,
            channel=self.channel,
            expires_at=self.expires_at,
            one_time=self.one_time,
            consumed_at=consumed_at,
            policy_constraints=self.policy_constraints,
            signer_key_id=self.signer_key_id,
            payload_version=self.payload_version,
        )


@dataclass(frozen=True)
class SignedApprovalGrant:
    """Signed grant envelope."""

    payload: GrantPayload
    signature: str
    signature_algorithm: str

    def __post_init__(self) -> None:
        if not self.signature:
            raise ValueError("signature is required")
        if not self.signature_algorithm:
            raise ValueError("signature algorithm is required")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe signed grant envelope."""

        return {
            "payload": self.payload.to_dict(),
            "signature": self.signature,
            "signature_algorithm": self.signature_algorithm,
        }

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> "SignedApprovalGrant":
        """Build a signed grant from a JSON-safe mapping."""

        payload = values.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("signed grant payload is required")
        return cls(
            payload=GrantPayload.from_dict(payload),
            signature=_required_str(values, "signature"),
            signature_algorithm=_required_str(values, "signature_algorithm"),
        )


@dataclass(frozen=True)
class GrantVerificationResult:
    """Result of signed grant verification."""

    status: GrantVerificationStatus
    reason: str
    request_id: str | None = None
    grant_id: str | None = None
    signer_key_id: str | None = None

    @property
    def valid(self) -> bool:
        """Return whether verification succeeded."""

        return self.status == GrantVerificationStatus.VALID

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe result."""

        return {
            "status": self.status.value,
            "reason": self.reason,
            "request_id": self.request_id,
            "grant_id": self.grant_id,
            "signer_key_id": self.signer_key_id,
        }


def _required_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("mapping value is required")
    return value


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("datetime value must be timezone-aware")
    return parsed


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional datetime must be a string")
    return _parse_datetime(value)
