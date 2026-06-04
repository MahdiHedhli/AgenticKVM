"""Control-plane vocabulary and initial policy-core exports."""

from __future__ import annotations

CONTROL_MODES = (
    "Observe",
    "Assisted",
    "Supervised",
    "Full Control",
    "Custom",
)

INTERNAL_DECISIONS = (
    "deny",
    "ask_each_time",
    "ask_once_per_session",
    "allow",
    "allow_with_limits",
)

UNKNOWN_CAPABILITY_DECISION = "deny"

CAPABILITY_FAMILIES = (
    "session",
    "observe",
    "input",
    "power",
    "media",
    "boot",
    "bios",
    "firmware",
    "storage",
    "network",
    "bmc",
    "secrets",
    "runtime",
)

DANGEROUS_ACTIONS = (
    "force power actions",
    "NMI",
    "BMC reset",
    "arbitrary ISO mount",
    "boot override",
    "BIOS changes",
    "firmware updates",
    "network/BMC IP changes",
    "BMC credential changes",
    "disk format/wipe/repartition",
    "backup restore",
    "encryption changes",
    "raw secret reveal",
    "untrusted script/playbook execution",
    "external webhook calls",
    "subagent spawning",
)

HARD_INVARIANTS = (
    "Agent cannot change its own policy.",
    "Agent cannot disable audit logging.",
    "Agent cannot disable emergency stop.",
    "Agent cannot silently expand target scope.",
    "Agent cannot silently add credentials.",
    "Agent cannot reveal raw secrets by default.",
    "Agent cannot persist new background services without logging them.",
    "Agent cannot move to another target unless it is inside session scope.",
    "Agent cannot erase audit artifacts.",
    "Agent cannot hide material risk from the operator.",
    (
        "Agent cannot run destructive OOB actions against real hardware unless "
        "target and session scope explicitly allow it."
    ),
    (
        "Agent cannot treat provider-specific reset, boot, firmware, or storage "
        "actions as generic low-risk actions."
    ),
)

REQUIRED_FLOW = (
    "agent/tool request",
    "capability request",
    "policy decision",
    "operator approval if required",
    "provider adapter",
    "structured audit event",
    "result",
)


def default_decision_for_unknown_capability(_: str) -> str:
    """Return the constitutional default for an unknown capability."""

    return UNKNOWN_CAPABILITY_DECISION


from agentickvm.control_plane.capabilities import (  # noqa: E402
    DEFAULT_CAPABILITY_REGISTRY,
    Capability,
    CapabilityRegistry,
    RiskLevel,
)
from agentickvm.control_plane.decisions import (  # noqa: E402
    ControlMode,
    PolicyDecision,
)
from agentickvm.control_plane.policy import (  # noqa: E402
    CapabilityPolicy,
    PolicyDecisionResult,
    PolicyRule,
    SessionScope,
    TargetScope,
    load_policy_file,
    mode_preset,
)
from agentickvm.control_plane.targets import (  # noqa: E402
    TargetDefinition,
    TargetRegistry,
    TargetRegistryError,
)
from agentickvm.control_plane.approvals import (  # noqa: E402
    APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES,
    Actor,
    ActorType,
    ApprovalGrant,
    ApprovalGrantScope,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStore,
    CapabilityRef,
    EmergencyStopActive,
    EmergencyStopState,
    SessionApprovalGrant,
    build_approval_request,
    fingerprint_parameters,
)
from agentickvm.control_plane.audit import (  # noqa: E402
    AuditEvent,
    AuditEventType,
    AuditSink,
    InMemoryAuditSink,
    LocalJSONLAuditSink,
    ProviderRef,
    build_audit_event,
    redact_mapping,
    verify_audit_chain,
)
from agentickvm.control_plane.audit_checkpoint import (  # noqa: E402
    AuditCheckpoint,
    AuditCheckpointError,
    AuditCheckpointVerification,
    create_audit_checkpoint,
    verify_audit_checkpoint,
)
from agentickvm.control_plane.audit_export import (  # noqa: E402
    AuditExportError,
    AuditExportVerification,
    export_audit_log,
    verify_audit_export,
)
from agentickvm.control_plane.engine import (  # noqa: E402
    CapabilityRequest,
    ControlPlane,
    ControlPlaneResult,
    ControlPlaneStatus,
)

__all__ = [
    "APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES",
    "Actor",
    "ActorType",
    "ApprovalGrant",
    "ApprovalGrantScope",
    "ApprovalOutcome",
    "ApprovalRequest",
    "ApprovalResponse",
    "ApprovalStore",
    "AuditEvent",
    "AuditEventType",
    "AuditCheckpoint",
    "AuditCheckpointError",
    "AuditCheckpointVerification",
    "AuditExportError",
    "AuditExportVerification",
    "AuditSink",
    "CAPABILITY_FAMILIES",
    "CONTROL_MODES",
    "DANGEROUS_ACTIONS",
    "DEFAULT_CAPABILITY_REGISTRY",
    "EmergencyStopActive",
    "EmergencyStopState",
    "HARD_INVARIANTS",
    "InMemoryAuditSink",
    "INTERNAL_DECISIONS",
    "LocalJSONLAuditSink",
    "ProviderRef",
    "REQUIRED_FLOW",
    "SessionApprovalGrant",
    "UNKNOWN_CAPABILITY_DECISION",
    "Capability",
    "CapabilityRef",
    "CapabilityRequest",
    "CapabilityPolicy",
    "CapabilityRegistry",
    "ControlPlane",
    "ControlPlaneResult",
    "ControlPlaneStatus",
    "ControlMode",
    "PolicyDecision",
    "PolicyDecisionResult",
    "PolicyRule",
    "RiskLevel",
    "SessionScope",
    "TargetScope",
    "TargetDefinition",
    "TargetRegistry",
    "TargetRegistryError",
    "build_approval_request",
    "build_audit_event",
    "create_audit_checkpoint",
    "export_audit_log",
    "default_decision_for_unknown_capability",
    "fingerprint_parameters",
    "load_policy_file",
    "mode_preset",
    "redact_mapping",
    "verify_audit_checkpoint",
    "verify_audit_export",
    "verify_audit_chain",
]
