"""Parity tests for the ACT params_fingerprint / extensions_digest / short_code.

ACT computes these authoritatively from the redacted payload and extensions the
aircraft sends. For the aircraft's clearance binding to hold against a live ACT
response, the aircraft must predict them with the exact same algorithm. These
tests pin the aircraft implementation to the published ACT contract algorithm
(``json.dumps`` canonical JSON + SHA-256; see the Tower's
``clearance_contract.build_params_fingerprint`` / ``security.content_hash``).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from agentickvm.control_plane import (
    act_content_hash,
    act_extensions_digest,
    act_params_fingerprint,
    act_short_code,
    build_clearance_request,
)
from agentickvm.control_plane.act_http_client import (
    act_payload_redacted,
    act_request_extensions,
    clearance_request_to_act_payload,
    predicted_act_params_fingerprint,
    predicted_act_short_code,
)

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


def _act_reference_canonical(value) -> str:
    # The exact canonicalization the Tower contract uses.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _act_reference_content_hash(value) -> str:
    return hashlib.sha256(_act_reference_canonical(value).encode("utf-8")).hexdigest()


def _act_reference_params_fingerprint(payload_redacted, extensions) -> str:
    return _act_reference_content_hash(
        {"payload_redacted": payload_redacted, "extensions": extensions or {}}
    )


def _request(**overrides):
    params = {
        "session_id": "session-1",
        "target": "mock-host",
        "provider": "mock",
        "capability": "power.force_restart",
        "parameters": {"reason": "wedged"},
        "risk_family": "high_risk",
        "risk_summary": "forced restart",
        "material_risks": ("availability disruption",),
        "intended_effect": "recover wedged machine",
        "requested_by": "agent",
        "audit_correlation_id": "corr-1",
        "policy_context": {"decision": "ask_each_time"},
        "now": NOW,
        "request_id": "request-1",
    }
    params.update(overrides)
    return build_clearance_request(**params)


def test_params_fingerprint_matches_act_reference_algorithm() -> None:
    payload_redacted = {"capability": "power.force_restart"}
    extensions = {"agentickvm": {"target": "mock-host", "capability": "power.force_restart"}}

    assert act_params_fingerprint(
        payload_redacted=payload_redacted, extensions=extensions
    ) == _act_reference_params_fingerprint(payload_redacted, extensions)


def test_content_hash_matches_act_reference() -> None:
    value = {"b": 2, "a": [3, 1], "nested": {"y": 1, "x": 2}}

    assert act_content_hash(value) == _act_reference_content_hash(value)


def test_canonical_json_is_key_order_independent() -> None:
    # Sorted-key canonicalization: input dict order must not change the hash.
    a = {"x": 1, "y": {"b": 2, "a": 1}}
    b = {"y": {"a": 1, "b": 2}, "x": 1}

    assert act_params_fingerprint(payload_redacted=a, extensions=None) == act_params_fingerprint(
        payload_redacted=b, extensions=None
    )


def test_extensions_digest_matches_act_reference() -> None:
    extensions = {"agentickvm": {"target": "mock-host", "policy_context": {"decision": "ask"}}}

    assert act_extensions_digest(extensions) == _act_reference_content_hash(extensions)
    assert act_extensions_digest(None) == _act_reference_content_hash({})


def test_short_code_matches_act_reference_and_is_ten_hex() -> None:
    fingerprint = "a" * 64
    expected = hashlib.sha256(f"appr-1:{fingerprint}".encode("utf-8")).hexdigest()[:10]

    code = act_short_code("appr-1", fingerprint)
    assert code == expected
    assert len(code) == 10
    assert all(ch in "0123456789abcdef" for ch in code)


def test_predicted_fingerprint_covers_exactly_what_the_client_sends() -> None:
    # The fingerprint the aircraft predicts must be computed over exactly the
    # redacted payload + extensions the real client puts on the wire.
    request = _request()
    payload = clearance_request_to_act_payload(
        request, agent_id="agentickvm", expires_in_seconds=20
    )

    predicted = predicted_act_params_fingerprint(request)
    over_the_wire = _act_reference_params_fingerprint(
        payload["payload_redacted"], payload["extensions"]
    )

    assert predicted == over_the_wire
    assert act_payload_redacted(request) == payload["payload_redacted"]
    assert act_request_extensions(request) == payload["extensions"]


def test_predicted_short_code_binds_request_id_and_fingerprint() -> None:
    request = _request()

    assert predicted_act_short_code(request) == act_short_code(
        request.request_id, predicted_act_params_fingerprint(request)
    )
    # An ACT-assigned approval_id can override the request_id binding.
    assert predicted_act_short_code(request, approval_id="appr-xyz") == act_short_code(
        "appr-xyz", predicted_act_params_fingerprint(request)
    )
