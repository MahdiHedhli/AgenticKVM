"""ACT-parity params fingerprint, extensions digest, and short code.

ACT computes ``params_fingerprint``, ``extensions_digest``, and the operator
``short_code`` authoritatively from the redacted payload and extensions envelope
the aircraft sends -- it ignores any aircraft-supplied fingerprint. For the
aircraft's clearance binding to hold against a live ACT response, the aircraft
must *predict* those values using the exact same algorithm.

This module mirrors the published ACT clearance contract's computation
(``act.clearance.v2``; Tower ``clearance_contract.build_params_fingerprint`` /
``security.content_hash``). Canonical JSON is ``json.dumps`` with sorted keys,
tight separators, and ``default=str``. Keep this aligned with the Tower contract;
the canonicalization is part of the wire agreement, not a local choice.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def act_canonical_json(value: Any) -> str:
    """Return ACT's canonical JSON encoding of a value."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def act_content_hash(value: Any) -> str:
    """Return the SHA-256 hex digest of a value's ACT canonical JSON."""

    return hashlib.sha256(act_canonical_json(value).encode("utf-8")).hexdigest()


def act_params_fingerprint(
    *,
    payload_redacted: Mapping[str, Any],
    extensions: Mapping[str, Any] | None,
) -> str:
    """Predict ACT's params_fingerprint for a redacted payload + extensions."""

    return act_content_hash(
        {
            "payload_redacted": dict(payload_redacted),
            "extensions": dict(extensions) if extensions else {},
        }
    )


def act_extensions_digest(extensions: Mapping[str, Any] | None) -> str:
    """Predict ACT's extensions_digest (content hash of the extensions object)."""

    return act_content_hash(dict(extensions) if extensions else {})


def act_short_code(approval_id: str, params_fingerprint: str) -> str:
    """Predict ACT's operator short code (first 10 hex of a bound SHA-256)."""

    return hashlib.sha256(
        f"{approval_id}:{params_fingerprint}".encode("utf-8")
    ).hexdigest()[:10]


def act_agentickvm_extensions(
    *,
    target: str | None,
    provider: str | None,
    capability: str | None,
    risk_summary: str | None,
    policy_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the ``extensions.agentickvm`` envelope the aircraft sends to ACT."""

    return {
        "agentickvm": {
            "target": target,
            "provider": provider,
            "capability": capability,
            "risk_summary": risk_summary,
            "policy_context": dict(policy_context) if policy_context else {},
        }
    }


__all__ = [
    "act_agentickvm_extensions",
    "act_canonical_json",
    "act_content_hash",
    "act_extensions_digest",
    "act_params_fingerprint",
    "act_short_code",
]
