import time
from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane import (
    ApprovalBroker,
    ApprovalChannel,
    DEFAULT_APPROVAL_TIMEOUT_SECONDS,
)


NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


def _broker() -> ApprovalBroker:
    return ApprovalBroker(id_factory=lambda: "approval-1")


def test_approval_request_returns_approval_required_with_short_code() -> None:
    request = _broker().request_approval(
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters={"force": True},
        risk_family="power",
        risk_summary="Restarting this machine may disrupt availability.",
        material_risks=("availability disruption",),
        intended_effect="recover wedged mock fixture.",
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    payload = request.to_approval_required()
    approval = payload["approval_request"]

    assert payload["status"] == "approval_required"
    assert approval["id"] == "approval-1"
    assert approval["short_code"] == request.short_code.value
    assert approval["risk_family"] == "power"
    assert approval["channel"] == "out_of_band"
    assert approval["timeout_seconds"] == DEFAULT_APPROVAL_TIMEOUT_SECONDS
    assert "re-call the same tool" in approval["retry_instructions"]
    assert ".." not in approval["operator_message"]


def test_approval_request_binds_parameter_fingerprint() -> None:
    first = _broker().request_approval(
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters={"a": 1, "b": 2},
        risk_family="power",
        risk_summary="Power action.",
        material_risks=("availability disruption",),
        intended_effect="recover fixture",
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    second = _broker().request_approval(
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters={"b": 2, "a": 1},
        risk_family="power",
        risk_summary="Power action.",
        material_risks=("availability disruption",),
        intended_effect="recover fixture",
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    changed = _broker().request_approval(
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters={"a": 1, "b": 3},
        risk_family="power",
        risk_summary="Power action.",
        material_risks=("availability disruption",),
        intended_effect="recover fixture",
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )

    assert first.params_fingerprint == second.params_fingerprint
    assert first.params_fingerprint != changed.params_fingerprint


def test_approval_request_returns_without_waiting_for_operator() -> None:
    start = time.monotonic()

    _broker().request_approval(
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters={},
        risk_family="power",
        risk_summary="Power action.",
        material_risks=("availability disruption",),
        intended_effect="recover fixture",
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )

    assert time.monotonic() - start < 0.5


def test_approval_timeout_is_configurable_but_bounded() -> None:
    assert ApprovalBroker(timeout_seconds=5).timeout_seconds == 5

    with pytest.raises(ValueError, match="timeout cannot exceed"):
        ApprovalBroker(timeout_seconds=DEFAULT_APPROVAL_TIMEOUT_SECONDS + 1)


def test_approval_request_can_represent_watch_tui_channel() -> None:
    request = _broker().request_approval(
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="observe.status",
        parameters={},
        risk_family="observe",
        risk_summary="Low-risk observe action.",
        material_risks=("operator visibility",),
        intended_effect="inspect status",
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
        channel=ApprovalChannel.WATCH_TUI,
    )

    assert request.to_approval_required()["approval_request"]["channel"] == "watch_tui"
