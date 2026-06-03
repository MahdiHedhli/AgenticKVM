from agentickvm.control_plane import (
    Actor,
    ActorType,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    TargetScope,
    mode_preset,
)
from agentickvm.providers import MockProvider


class RealHardwareLikeProvider(MockProvider):
    provider_id = "real-like"
    provider_kind = "test-real-like"
    is_real_hardware = True


def _request(capability_id: str, *, target_id: str = "lab-a") -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id=target_id,
        session_id="s1",
        correlation_id="corr-sec",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        intended_effect="security test",
    )


def test_policy_denial_prevents_provider_execution() -> None:
    provider = MockProvider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.OBSERVE),
        provider=provider,
        audit_sink=InMemoryAuditSink(),
    )

    result = engine.handle(_request("power.force_off"))

    assert result.status == ControlPlaneStatus.DENIED
    assert provider.requests == []


def test_real_hardware_provider_denied_unless_policy_scope_allows_it() -> None:
    provider = RealHardwareLikeProvider()
    policy = mode_preset(ControlMode.FULL_CONTROL)
    engine = ControlPlane(
        policy=policy,
        provider=provider,
        audit_sink=InMemoryAuditSink(),
    )

    result = engine.handle(_request("observe.status"))

    assert result.status == ControlPlaneStatus.DENIED
    assert result.decision.reason == "real hardware provider outside policy scope"
    assert provider.requests == []


def test_real_hardware_scope_is_explicit() -> None:
    provider = RealHardwareLikeProvider()
    policy = mode_preset(ControlMode.FULL_CONTROL)
    explicit_policy = policy.__class__(
        name=policy.name,
        mode=policy.mode,
        target_scope=TargetScope(allow_real_hardware=True),
        session_scope=policy.session_scope,
        rules=policy.rules,
    )
    engine = ControlPlane(
        policy=explicit_policy,
        provider=provider,
        audit_sink=InMemoryAuditSink(),
    )

    result = engine.handle(_request("observe.status"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert provider.requests[0].capability == "observe.status"
