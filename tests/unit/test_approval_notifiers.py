from datetime import UTC, datetime, timedelta

from agentickvm.control_plane import ApprovalBroker, LocalApprovalNotifier


NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


def test_local_approval_notifier_renders_allow_and_deny_without_network() -> None:
    broker = ApprovalBroker(id_factory=lambda: "approval-1")
    request = broker.request_approval(
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters={"force": True},
        risk_family="power",
        risk_summary="Restarting this machine may disrupt availability.",
        material_risks=("availability disruption",),
        intended_effect="recover wedged mock fixture",
        now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    notifier = LocalApprovalNotifier()

    notification = notifier.notify(request)
    payload = notification.to_dict()

    assert len(notifier.sent) == 1
    assert payload["request_id"] == "approval-1"
    assert payload["short_code"] == request.short_code.value
    assert payload["allow_action"]["action"] == "allow"
    assert payload["deny_action"]["action"] == "deny"
    assert "secret" not in str(payload).lower()
