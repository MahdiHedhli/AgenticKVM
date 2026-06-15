"""AgenticKVM-side risk-family labels for ACT clearance requests.

ACT owns channel and tier decisions. AgenticKVM only labels clearance requests
with an explicit risk family so the tower never has to derive a permissive
default from an omitted field.
"""

from __future__ import annotations

from agentickvm.control_plane.capabilities import Capability
from agentickvm.control_plane.clearance import ClearanceRiskFamily


LOW_RISK_CAPABILITY_IDS = frozenset(
    {
        "observe.status",
        "observe.screen",
        "observe.screenshot",
        "observe.power_state",
        "observe.hardware_inventory",
        "observe.sensors",
        "observe.event_logs",
        "observe.boot_status",
        "bios.view_settings",
        "storage.view_disk_layout",
        "network.read_config",
        "bmc.account_list",
        "runtime.request_clearance",
        "runtime.deny_clearance",
    }
)

HIGH_RISK_CAPABILITY_FAMILIES = frozenset(
    {
        "input",
        "power",
        "media",
        "boot",
        "firmware",
        "secrets",
    }
)

HIGH_RISK_CAPABILITY_IDS = frozenset(
    {
        "session.modify_policy",
        "session.disable_audit",
        "session.disable_emergency_stop",
        "bios.change_setting",
        "storage.wipe_disk",
        "storage.repartition_disk",
        "storage.restore_backup",
        "network.change_bmc_ip",
        "network.change_host_ip",
        "bmc.rotate_password",
        "bmc.reset",
        "runtime.run_approved_playbook",
        "runtime.execute_untrusted_script",
        "runtime.call_external_webhook",
        "runtime.spawn_subagent",
    }
)


def clearance_risk_family_for_capability(capability: Capability | None) -> ClearanceRiskFamily:
    """Return the explicit risk family AgenticKVM sends to ACT.

    Unknown or unmapped capabilities fail toward the restrictive high-risk
    family. AgenticKVM does not choose the operator channel or tier here; ACT
    owns that decision.
    """

    if capability is None:
        return ClearanceRiskFamily.HIGH_RISK
    if capability.id in LOW_RISK_CAPABILITY_IDS:
        return ClearanceRiskFamily.LOW_RISK
    if capability.id in HIGH_RISK_CAPABILITY_IDS:
        return ClearanceRiskFamily.HIGH_RISK
    if capability.family in HIGH_RISK_CAPABILITY_FAMILIES:
        return ClearanceRiskFamily.HIGH_RISK
    return ClearanceRiskFamily.HIGH_RISK
