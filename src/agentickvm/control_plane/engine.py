"""Minimal control-plane orchestrator for mock-only execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.control_plane import CAPABILITY_FAMILIES
from agentickvm.control_plane.approvals import (
    Actor,
    ApprovalRequest,
    ApprovalStore,
    CapabilityRef,
    build_approval_request,
    fingerprint_parameters,
)
from agentickvm.control_plane.approval_broker import (
    ApprovalGrantVerifier,
    GrantVerificationContext,
)
from agentickvm.control_plane.audit import (
    AuditEventType,
    AuditSink,
    ProviderRef,
    build_audit_event,
)
from agentickvm.control_plane.grants import SignedApprovalGrant
from agentickvm.control_plane.capabilities import (
    Capability,
    CapabilityRegistry,
    DEFAULT_CAPABILITY_REGISTRY,
)
from agentickvm.control_plane.decisions import PolicyDecision
from agentickvm.control_plane.policy import CapabilityPolicy, PolicyDecisionResult
from agentickvm.providers.base import (
    Provider,
    ProviderActionRequest,
    ProviderActionResult,
)


class ControlPlaneStatus(StrEnum):
    """Control-plane request outcome."""

    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class CapabilityRequest:
    """Provider-neutral request entering the control plane."""

    capability_id: str
    target_id: str
    session_id: str
    correlation_id: str
    requester: Actor
    intended_effect: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    credential_id: str | None = None
    approval_request_id: str | None = None
    signed_approval_grant: SignedApprovalGrant | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True)
class ControlPlaneResult:
    """Structured result returned by the control plane."""

    status: ControlPlaneStatus
    decision: PolicyDecisionResult
    approval_request: ApprovalRequest | None = None
    provider_result: ProviderActionResult | None = None
    message: str = ""


class ControlPlane:
    """Evaluate policy, approval needs, audit, and provider execution."""

    def __init__(
        self,
        *,
        policy: CapabilityPolicy,
        provider: Provider,
        audit_sink: AuditSink,
        registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
        approval_store: ApprovalStore | None = None,
        now_factory: Any | None = None,
        approval_grant_verifier: ApprovalGrantVerifier | None = None,
    ) -> None:
        self.policy = policy
        self.provider = provider
        self.audit_sink = audit_sink
        self.registry = registry
        self.approval_store = approval_store
        self.now_factory = now_factory or (lambda: datetime.now(UTC))
        self.approval_grant_verifier = approval_grant_verifier
        self._consumed_signed_grant_ids: set[str] = set()

    def handle(self, request: CapabilityRequest) -> ControlPlaneResult:
        """Handle a capability request through the required control flow."""

        capability = self.registry.get(request.capability_id)
        decision = self.policy.decision_for(
            request.capability_id,
            target_id=request.target_id,
            session_id=request.session_id,
            credential_id=request.credential_id,
            registry=self.registry,
        )
        capability_ref = _capability_ref(request.capability_id, capability)

        self._emit(
            event_type=AuditEventType.REQUEST_RECEIVED,
            request=request,
            capability_ref=capability_ref,
            policy_decision=decision.decision,
            request_payload={
                "capability_id": request.capability_id,
                "parameters": dict(request.parameters),
                "intended_effect": request.intended_effect,
            },
            material_risks=decision.material_risks,
        )

        self._emit(
            event_type=(
                AuditEventType.CAPABILITY_RESOLVED
                if capability is not None
                else AuditEventType.CAPABILITY_UNKNOWN_DENIED
            ),
            request=request,
            capability_ref=capability_ref,
            policy_decision=decision.decision,
            material_risks=decision.material_risks,
        )

        self._emit(
            event_type=AuditEventType.POLICY_DECISION,
            request=request,
            capability_ref=capability_ref,
            policy_decision=decision.decision,
            result_payload={
                "decision": decision.decision.value,
                "reason": decision.reason,
            },
            material_risks=decision.material_risks,
        )

        if decision.decision == PolicyDecision.DENY:
            self._emit_result_returned(request, capability_ref, decision, ControlPlaneStatus.DENIED)
            return ControlPlaneResult(
                status=ControlPlaneStatus.DENIED,
                decision=decision,
                message=decision.reason,
            )

        if self.provider.is_real_hardware and not self.policy.target_scope.allow_real_hardware:
            hardware_decision = PolicyDecisionResult(
                capability_id=request.capability_id,
                decision=PolicyDecision.DENY,
                reason="real hardware provider outside policy scope",
                material_risks=decision.material_risks,
            )
            self._emit_result_returned(
                request,
                capability_ref,
                hardware_decision,
                ControlPlaneStatus.DENIED,
            )
            return ControlPlaneResult(
                status=ControlPlaneStatus.DENIED,
                decision=hardware_decision,
                message=hardware_decision.reason,
            )

        if decision.requires_approval:
            if capability is None:
                raise RuntimeError("Unknown capabilities cannot require approval")
            signed_result = self._verify_signed_approval_grant(
                request=request,
                capability_ref=capability_ref,
                decision=decision,
            )
            if signed_result is True:
                return self._execute_provider(
                    request=request,
                    capability=capability,
                    capability_ref=capability_ref,
                    decision=decision,
                )
            grant = self._matching_approval_grant(request)
            if grant is not None:
                if self.approval_store is None:
                    raise RuntimeError("Approval grant found without approval store")
                self.approval_store.consume(grant)
                self._emit(
                    event_type=AuditEventType.APPROVAL_CONSUMED,
                    request=request,
                    capability_ref=capability_ref,
                    policy_decision=decision.decision,
                    approval_payload=grant.to_dict(),
                    material_risks=decision.material_risks,
                )
                return self._execute_provider(
                    request=request,
                    capability=capability,
                    capability_ref=capability_ref,
                    decision=decision,
                )

            approval_request = build_approval_request(
                decision_result=decision,
                capability=capability,
                session_id=request.session_id,
                requester=request.requester,
                target_ids=(request.target_id,),
                intended_effect=request.intended_effect,
                provider_id=self.provider.provider_id,
                now=self.now_factory(),
            )
            self._emit(
                event_type=AuditEventType.APPROVAL_REQUESTED,
                request=request,
                capability_ref=capability_ref,
                policy_decision=decision.decision,
                approval_payload=approval_request.to_dict(),
                material_risks=decision.material_risks,
            )
            self._emit_result_returned(
                request,
                capability_ref,
                decision,
                ControlPlaneStatus.APPROVAL_REQUIRED,
            )
            return ControlPlaneResult(
                status=ControlPlaneStatus.APPROVAL_REQUIRED,
                decision=decision,
                approval_request=approval_request,
                message="operator approval required",
            )

        if capability is None:
            raise RuntimeError("Unknown capability reached provider execution")

        return self._execute_provider(
            request=request,
            capability=capability,
            capability_ref=capability_ref,
            decision=decision,
        )

    def _execute_provider(
        self,
        *,
        request: CapabilityRequest,
        capability: Capability,
        capability_ref: CapabilityRef,
        decision: PolicyDecisionResult,
    ) -> ControlPlaneResult:
        provider_request = ProviderActionRequest(
            capability=capability.id,
            action=capability.action,
            target_id=request.target_id,
            session_id=request.session_id,
            correlation_id=request.correlation_id,
            parameters=request.parameters,
        )
        provider_ref = ProviderRef(
            id=self.provider.provider_id,
            kind=self.provider.provider_kind,
            is_real_hardware=self.provider.is_real_hardware,
        )
        self._emit(
            event_type=AuditEventType.PROVIDER_EXECUTION_STARTED,
            request=request,
            capability_ref=capability_ref,
            policy_decision=decision.decision,
            provider_ref=provider_ref,
            material_risks=decision.material_risks,
        )
        provider_result = self.provider.execute_authorized(provider_request)
        self._emit(
            event_type=(
                AuditEventType.PROVIDER_EXECUTION_COMPLETED
                if provider_result.ok
                else AuditEventType.PROVIDER_EXECUTION_FAILED
            ),
            request=request,
            capability_ref=capability_ref,
            policy_decision=decision.decision,
            provider_ref=provider_ref,
            result_payload=_provider_audit_result_payload(provider_result),
            material_risks=decision.material_risks,
        )
        status = ControlPlaneStatus.COMPLETED if provider_result.ok else ControlPlaneStatus.FAILED
        self._emit_result_returned(request, capability_ref, decision, status)
        return ControlPlaneResult(
            status=status,
            decision=decision,
            provider_result=provider_result,
            message=provider_result.message,
        )

    def _matching_approval_grant(self, request: CapabilityRequest) -> Any | None:
        if self.approval_store is None:
            return None
        return self.approval_store.find_action_grant(
            capability_id=request.capability_id,
            session_id=request.session_id,
            target_id=request.target_id,
            provider_id=self.provider.provider_id,
            params_fingerprint=fingerprint_parameters(request.parameters),
            now=self.now_factory(),
        )

    def _verify_signed_approval_grant(
        self,
        *,
        request: CapabilityRequest,
        capability_ref: CapabilityRef,
        decision: PolicyDecisionResult,
    ) -> bool | None:
        if request.signed_approval_grant is None:
            return None
        if self.approval_grant_verifier is None:
            self._emit(
                event_type=AuditEventType.APPROVAL_REJECTED,
                request=request,
                capability_ref=capability_ref,
                policy_decision=decision.decision,
                approval_payload={"reason": "signed approval verifier is not configured"},
                material_risks=decision.material_risks,
            )
            return None
        if request.approval_request_id is None:
            self._emit(
                event_type=AuditEventType.APPROVAL_REJECTED,
                request=request,
                capability_ref=capability_ref,
                policy_decision=decision.decision,
                approval_payload={"reason": "approval request id is required"},
                material_risks=decision.material_risks,
            )
            return None
        grant_id = request.signed_approval_grant.payload.grant_id
        if grant_id in self._consumed_signed_grant_ids:
            self._emit(
                event_type=AuditEventType.APPROVAL_REJECTED,
                request=request,
                capability_ref=capability_ref,
                policy_decision=decision.decision,
                approval_payload={"grant_id": grant_id, "reason": "signed grant already consumed"},
                material_risks=decision.material_risks,
            )
            return None
        verification = self.approval_grant_verifier.verify(
            request.signed_approval_grant,
            context=GrantVerificationContext.from_parameters(
                request_id=request.approval_request_id,
                session_id=request.session_id,
                target=request.target_id,
                provider=self.provider.provider_id,
                capability=request.capability_id,
                parameters=request.parameters,
                risk_family=capability_ref.family,
                now=self.now_factory(),
            ),
        )
        event_type = (
            AuditEventType.APPROVAL_VERIFIED
            if verification.valid
            else AuditEventType.APPROVAL_REJECTED
        )
        self._emit(
            event_type=event_type,
            request=request,
            capability_ref=capability_ref,
            policy_decision=decision.decision,
            approval_payload=verification.to_dict(),
            material_risks=decision.material_risks,
        )
        if not verification.valid:
            return None
        if request.signed_approval_grant.payload.one_time:
            self._consumed_signed_grant_ids.add(grant_id)
            self._emit(
                event_type=AuditEventType.APPROVAL_CONSUMED,
                request=request,
                capability_ref=capability_ref,
                policy_decision=decision.decision,
                approval_payload=verification.to_dict(),
                material_risks=decision.material_risks,
            )
        return True

    def _emit(
        self,
        *,
        event_type: AuditEventType,
        request: CapabilityRequest,
        capability_ref: CapabilityRef,
        policy_decision: PolicyDecision,
        approval_payload: Mapping[str, Any] | None = None,
        provider_ref: ProviderRef | None = None,
        request_payload: Mapping[str, Any] | None = None,
        result_payload: Mapping[str, Any] | None = None,
        material_risks: tuple[str, ...] = (),
    ) -> None:
        event = build_audit_event(
            event_type=event_type,
            correlation_id=request.correlation_id,
            session_id=request.session_id,
            target_id=request.target_id,
            actor=request.requester,
            capability=capability_ref,
            policy_decision=policy_decision,
            request=request_payload,
            result=result_payload,
            material_risks=material_risks,
        )
        if approval_payload is not None or provider_ref is not None:
            event = event.__class__(
                id=event.id,
                timestamp=event.timestamp,
                event_type=event.event_type,
                correlation_id=event.correlation_id,
                session_id=event.session_id,
                actor=event.actor,
                capability=event.capability,
                policy_decision=event.policy_decision,
                redactions=event.redactions,
                target_id=event.target_id,
                approval=approval_payload,
                provider=provider_ref,
                request=event.request,
                result=event.result,
                material_risks=event.material_risks,
            )
        self.audit_sink.emit(event)

    def _emit_result_returned(
        self,
        request: CapabilityRequest,
        capability_ref: CapabilityRef,
        decision: PolicyDecisionResult,
        status: ControlPlaneStatus,
    ) -> None:
        self._emit(
            event_type=AuditEventType.RESULT_RETURNED,
            request=request,
            capability_ref=capability_ref,
            policy_decision=decision.decision,
            result_payload={"status": status.value, "reason": decision.reason},
            material_risks=decision.material_risks,
        )


def _capability_ref(capability_id: str, capability: Capability | None) -> CapabilityRef:
    if capability is not None:
        return CapabilityRef.from_capability(capability)

    family, _, action = capability_id.partition(".")
    if family not in CAPABILITY_FAMILIES:
        family = "runtime"
    return CapabilityRef(
        id=capability_id,
        family=family,
        action=action or "unknown",
    )


def _provider_audit_result_payload(
    provider_result: ProviderActionResult,
) -> Mapping[str, Any]:
    """Return provider execution audit metadata without raw provider payloads."""

    payload: dict[str, Any] = {
        "ok": provider_result.ok,
        "performed_on_hardware": provider_result.performed_on_hardware,
        "message": provider_result.message,
    }
    if provider_result.error_code is not None:
        payload["error_code"] = provider_result.error_code
        payload["retryable"] = provider_result.retryable
    artifacts = tuple(_artifact_metadata(provider_result.data))
    if artifacts:
        payload["artifacts"] = list(artifacts)
    return payload


def _artifact_metadata(value: Any) -> tuple[Mapping[str, Any], ...]:
    """Extract metadata-only artifact entries from nested provider data."""

    if isinstance(value, Mapping):
        artifacts: list[Mapping[str, Any]] = []
        artifact = value.get("artifact")
        if isinstance(artifact, Mapping):
            entry = dict(artifact)
            if "raw_bytes_included" in value and "raw_bytes_included" not in entry:
                entry["raw_bytes_included"] = value["raw_bytes_included"]
            artifacts.append(entry)
        for child in value.values():
            artifacts.extend(_artifact_metadata(child))
        return tuple(artifacts)
    if isinstance(value, (list, tuple)):
        artifacts: list[Mapping[str, Any]] = []
        for item in value:
            artifacts.extend(_artifact_metadata(item))
        return tuple(artifacts)
    return ()
