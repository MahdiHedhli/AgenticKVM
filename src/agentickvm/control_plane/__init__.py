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

__all__ = [
    "CAPABILITY_FAMILIES",
    "CONTROL_MODES",
    "DANGEROUS_ACTIONS",
    "DEFAULT_CAPABILITY_REGISTRY",
    "HARD_INVARIANTS",
    "INTERNAL_DECISIONS",
    "REQUIRED_FLOW",
    "UNKNOWN_CAPABILITY_DECISION",
    "Capability",
    "CapabilityPolicy",
    "CapabilityRegistry",
    "ControlMode",
    "PolicyDecision",
    "PolicyDecisionResult",
    "PolicyRule",
    "RiskLevel",
    "SessionScope",
    "TargetScope",
    "default_decision_for_unknown_capability",
    "load_policy_file",
    "mode_preset",
]
