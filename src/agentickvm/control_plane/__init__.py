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
from agentickvm.control_plane.auth_channel import (  # noqa: E402
    AuthChannel,
    AuthChannelError,
    AuthChannelSelection,
    DEFAULT_AUTH_CHANNEL,
    LOCAL_TERMINAL_WARNING,
    RECOMMENDED_AUTH_CHANNEL,
    resolve_auth_channel,
)
from agentickvm.control_plane.act_proof import (  # noqa: E402
    ACT_PROOF_CANONICALIZATION,
    ACTClearanceProofVerifier,
    ACTProofError,
    SUPPORTED_CONTRACT_VERSIONS,
    TowerKeyRegistry,
    build_clearance_proof_message,
    verify_clearance_proof,
)
from agentickvm.control_plane.act_fingerprint import (  # noqa: E402
    act_agentickvm_extensions,
    act_canonical_json,
    act_content_hash,
    act_extensions_digest,
    act_params_fingerprint,
    act_short_code,
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
from agentickvm.control_plane.approval_transport import (  # noqa: E402
    LocalApprovalQueue,
    LocalApprovalRecord,
    LocalApprovalStatus,
)
from agentickvm.control_plane.approval_broker import (  # noqa: E402
    ApprovalGrantVerifier,
    ApprovalBroker,
    ApprovalSigner,
    BrokerApprovalRequest,
    DEFAULT_APPROVAL_TIMEOUT_SECONDS,
    GrantVerificationContext,
    HMACDevelopmentSigner,
    build_grant_payload,
)
from agentickvm.control_plane.approval_store import (  # noqa: E402
    ApprovalCacheError,
    SignedApprovalCache,
)
from agentickvm.control_plane.act_client import (  # noqa: E402
    ACTClearanceVerifier,
    ACTPendingProofVerifier,
    ClearanceClient,
    ClearanceProofVerifier,
    MockACTClient,
    MockACTProofVerifier,
    cleared_response_for,
)
from agentickvm.control_plane.act_http_client import (  # noqa: E402
    ACTHTTPClearanceClient,
    ACTHTTPTransport,
    UrllibACTHTTPTransport,
    clearance_request_to_act_payload,
    predicted_act_params_fingerprint,
    predicted_act_short_code,
)
from agentickvm.control_plane.clearance import (  # noqa: E402
    ACT_AIRCRAFT_ID,
    AIRCRAFT_RISK_FAMILIES,
    CONTRACT_VERSION_V2,
    DEFAULT_CLEARANCE_TIMEOUT_SECONDS,
    TOWER_RESOLVED_RISK_FAMILIES,
    ClearanceOperatorMessage,
    ClearanceParamsFingerprint,
    ClearanceRequest,
    ClearanceResponse,
    ClearanceRiskFamily,
    ClearanceRiskSummary,
    ClearanceShortCode,
    ClearanceStatus,
    ClearanceVerificationResult,
    build_clearance_request,
    build_operator_message,
    clearance_response_from_act_payload,
)
from agentickvm.control_plane.fingerprints import (  # noqa: E402
    FingerprintError,
    canonical_json,
    fingerprint_parameters as fingerprint_broker_parameters,
)
from agentickvm.control_plane.grants import (  # noqa: E402
    ApprovalChannel,
    ApprovalRiskSummary,
    ApprovalShortCode,
    GrantDecision,
    GrantPayload,
    GrantScope,
    GrantVerificationResult,
    GrantVerificationStatus,
    SignedApprovalGrant,
)
from agentickvm.control_plane.notifiers import (  # noqa: E402
    ApprovalNotification,
    ApprovalNotifier,
    LocalApprovalNotifier,
)
from agentickvm.control_plane.risk_families import (  # noqa: E402
    clearance_risk_family_for_capability,
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
from agentickvm.control_plane.audit_retention import (  # noqa: E402
    AuditRetentionPolicy,
    AuditRetentionPolicyError,
    AuditRotationDecision,
)
from agentickvm.control_plane.audit_sqlite import (  # noqa: E402
    SQLiteAuditError,
    SQLiteAuditSink,
    SQLiteAuditVerification,
    create_sqlite_audit_checkpoint,
    export_sqlite_audit,
    inspect_sqlite_audit_event,
    list_sqlite_audit_events,
    verify_sqlite_audit_checkpoint,
    verify_sqlite_audit_chain,
)
from agentickvm.control_plane.engine import (  # noqa: E402
    CapabilityRequest,
    ControlPlane,
    ControlPlaneResult,
    ControlPlaneStatus,
)

__all__ = [
    "APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES",
    "ACT_AIRCRAFT_ID",
    "ACTClearanceVerifier",
    "ACTPendingProofVerifier",
    "AuthChannel",
    "AuthChannelError",
    "AuthChannelSelection",
    "DEFAULT_AUTH_CHANNEL",
    "LOCAL_TERMINAL_WARNING",
    "RECOMMENDED_AUTH_CHANNEL",
    "resolve_auth_channel",
    "ACT_PROOF_CANONICALIZATION",
    "ACTClearanceProofVerifier",
    "ACTProofError",
    "SUPPORTED_CONTRACT_VERSIONS",
    "TowerKeyRegistry",
    "build_clearance_proof_message",
    "verify_clearance_proof",
    "act_agentickvm_extensions",
    "act_canonical_json",
    "act_content_hash",
    "act_extensions_digest",
    "act_params_fingerprint",
    "act_short_code",
    "ACTHTTPClearanceClient",
    "ACTHTTPTransport",
    "UrllibACTHTTPTransport",
    "clearance_request_to_act_payload",
    "clearance_response_from_act_payload",
    "predicted_act_params_fingerprint",
    "predicted_act_short_code",
    "AIRCRAFT_RISK_FAMILIES",
    "TOWER_RESOLVED_RISK_FAMILIES",
    "CONTRACT_VERSION_V2",
    "Actor",
    "ActorType",
    "ApprovalGrant",
    "ApprovalGrantScope",
    "ApprovalOutcome",
    "ApprovalRequest",
    "ApprovalResponse",
    "ApprovalStore",
    "ApprovalGrantVerifier",
    "ApprovalNotification",
    "ApprovalNotifier",
    "ApprovalBroker",
    "ApprovalSigner",
    "BrokerApprovalRequest",
    "ClearanceClient",
    "ClearanceProofVerifier",
    "ClearanceOperatorMessage",
    "ClearanceParamsFingerprint",
    "ClearanceRequest",
    "ClearanceResponse",
    "ClearanceRiskFamily",
    "ClearanceRiskSummary",
    "ClearanceShortCode",
    "ClearanceStatus",
    "ClearanceVerificationResult",
    "ApprovalChannel",
    "ApprovalCacheError",
    "ApprovalRiskSummary",
    "ApprovalShortCode",
    "AuditEvent",
    "AuditEventType",
    "AuditCheckpoint",
    "AuditCheckpointError",
    "AuditCheckpointVerification",
    "AuditExportError",
    "AuditExportVerification",
    "AuditRetentionPolicy",
    "AuditRetentionPolicyError",
    "AuditRotationDecision",
    "AuditSink",
    "CAPABILITY_FAMILIES",
    "CONTROL_MODES",
    "DANGEROUS_ACTIONS",
    "DEFAULT_CAPABILITY_REGISTRY",
    "DEFAULT_APPROVAL_TIMEOUT_SECONDS",
    "DEFAULT_CLEARANCE_TIMEOUT_SECONDS",
    "EmergencyStopActive",
    "EmergencyStopState",
    "FingerprintError",
    "GrantDecision",
    "GrantPayload",
    "GrantScope",
    "GrantVerificationContext",
    "GrantVerificationResult",
    "GrantVerificationStatus",
    "HARD_INVARIANTS",
    "HMACDevelopmentSigner",
    "InMemoryAuditSink",
    "INTERNAL_DECISIONS",
    "LocalJSONLAuditSink",
    "LocalApprovalQueue",
    "LocalApprovalRecord",
    "LocalApprovalStatus",
    "LocalApprovalNotifier",
    "MockACTClient",
    "MockACTProofVerifier",
    "ProviderRef",
    "REQUIRED_FLOW",
    "SessionApprovalGrant",
    "SignedApprovalCache",
    "SignedApprovalGrant",
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
    "SQLiteAuditError",
    "SQLiteAuditSink",
    "SQLiteAuditVerification",
    "TargetScope",
    "TargetDefinition",
    "TargetRegistry",
    "TargetRegistryError",
    "build_approval_request",
    "build_audit_event",
    "build_clearance_request",
    "build_grant_payload",
    "build_operator_message",
    "clearance_risk_family_for_capability",
    "canonical_json",
    "cleared_response_for",
    "create_audit_checkpoint",
    "create_sqlite_audit_checkpoint",
    "export_audit_log",
    "export_sqlite_audit",
    "default_decision_for_unknown_capability",
    "fingerprint_parameters",
    "fingerprint_broker_parameters",
    "inspect_sqlite_audit_event",
    "list_sqlite_audit_events",
    "load_policy_file",
    "mode_preset",
    "redact_mapping",
    "verify_audit_checkpoint",
    "verify_audit_export",
    "verify_audit_chain",
    "verify_sqlite_audit_checkpoint",
    "verify_sqlite_audit_chain",
]
