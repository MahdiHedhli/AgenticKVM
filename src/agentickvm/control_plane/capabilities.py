"""Capability registry for the initial AgenticKVM control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Iterable, Mapping

from agentickvm.control_plane import CAPABILITY_FAMILIES


class RiskLevel(StrEnum):
    """Provider-neutral capability risk labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Capability:
    """Provider-neutral action that policy can evaluate."""

    id: str
    family: str
    action: str
    title: str
    description: str
    risk: RiskLevel
    dangerous: bool = False
    destructive: bool = False
    required_scope: tuple[str, ...] = ()
    audit_fields: tuple[str, ...] = ("capability", "target_id", "session_id")

    def __post_init__(self) -> None:
        if self.family not in CAPABILITY_FAMILIES:
            raise ValueError(f"Unknown capability family: {self.family}")
        if "." not in self.id:
            raise ValueError(f"Capability id must be family.action: {self.id}")
        prefix, action = self.id.split(".", 1)
        if prefix != self.family:
            raise ValueError(f"Capability id family mismatch: {self.id}")
        if action != self.action:
            raise ValueError(f"Capability action mismatch: {self.id}")


class CapabilityRegistry:
    """Immutable lookup table for known capabilities."""

    def __init__(self, capabilities: Iterable[Capability]) -> None:
        registry: dict[str, Capability] = {}
        for capability in capabilities:
            if capability.id in registry:
                raise ValueError(f"Duplicate capability id: {capability.id}")
            registry[capability.id] = capability
        self._capabilities: Mapping[str, Capability] = MappingProxyType(registry)

    @property
    def capabilities(self) -> Mapping[str, Capability]:
        """Return the known capability mapping."""

        return self._capabilities

    def get(self, capability_id: str) -> Capability | None:
        """Return a capability, or None when it is unknown."""

        return self._capabilities.get(capability_id)

    def require(self, capability_id: str) -> Capability:
        """Return a capability or raise for caller-side validation."""

        capability = self.get(capability_id)
        if capability is None:
            raise KeyError(capability_id)
        return capability

    def families(self) -> frozenset[str]:
        """Return capability families represented by the registry."""

        return frozenset(capability.family for capability in self._capabilities.values())


def _capability(
    capability_id: str,
    title: str,
    description: str,
    risk: RiskLevel,
    *,
    dangerous: bool = False,
    destructive: bool = False,
    required_scope: tuple[str, ...] = ("target", "session"),
) -> Capability:
    family, action = capability_id.split(".", 1)
    return Capability(
        id=capability_id,
        family=family,
        action=action,
        title=title,
        description=description,
        risk=risk,
        dangerous=dangerous,
        destructive=destructive,
        required_scope=required_scope,
    )


DEFAULT_CAPABILITIES: tuple[Capability, ...] = (
    _capability(
        "session.start",
        "Start session",
        "Open a scoped operator session.",
        RiskLevel.LOW,
        required_scope=("session",),
    ),
    _capability(
        "session.end",
        "End session",
        "Close a scoped operator session.",
        RiskLevel.LOW,
        required_scope=("session",),
    ),
    _capability(
        "session.select_target",
        "Select target",
        "Select an in-scope target for a session.",
        RiskLevel.MEDIUM,
        required_scope=("target", "session"),
    ),
    _capability(
        "session.modify_policy",
        "Modify active policy",
        "Change the active policy for the requesting agent.",
        RiskLevel.CRITICAL,
        dangerous=True,
        required_scope=("session",),
    ),
    _capability(
        "session.disable_audit",
        "Disable audit",
        "Disable audit logging for the active session.",
        RiskLevel.CRITICAL,
        dangerous=True,
        required_scope=("session",),
    ),
    _capability(
        "session.disable_emergency_stop",
        "Disable emergency stop",
        "Disable emergency stop for the active session.",
        RiskLevel.CRITICAL,
        dangerous=True,
        required_scope=("session",),
    ),
    _capability(
        "observe.status",
        "Observe status",
        "Read a provider-neutral target status summary.",
        RiskLevel.LOW,
    ),
    _capability(
        "observe.screen",
        "Observe screen",
        "Read provider-neutral screen metadata or text without input.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "observe.screenshot",
        "Observe screenshot",
        "Capture or retrieve a current screen observation.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "observe.power_state",
        "Observe power state",
        "Read target power state.",
        RiskLevel.LOW,
    ),
    _capability(
        "observe.hardware_inventory",
        "Observe hardware inventory",
        "Read non-secret hardware inventory.",
        RiskLevel.LOW,
    ),
    _capability(
        "observe.sensors",
        "Observe sensors",
        "Read thermal, power, fan, or health sensors.",
        RiskLevel.LOW,
    ),
    _capability(
        "observe.event_logs",
        "Observe event logs",
        "Read BMC or platform event logs.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "observe.boot_status",
        "Observe boot status",
        "Read boot phase or boot override status.",
        RiskLevel.LOW,
    ),
    _capability(
        "input.mouse_move",
        "Move mouse",
        "Move the remote pointer inside session scope.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "input.mouse_click",
        "Click mouse",
        "Click the remote pointer inside session scope.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "input.keyboard_type",
        "Type text",
        "Type text through a remote input device.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "input.keyboard_key",
        "Send keyboard key",
        "Send one non-secret key through a remote input device.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "input.keyboard_shortcut",
        "Send keyboard shortcut",
        "Send a keyboard shortcut through a remote input device.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "power.on",
        "Power on",
        "Power on an in-scope target.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "power.graceful_shutdown",
        "Graceful shutdown",
        "Request an orderly shutdown.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "power.graceful_restart",
        "Graceful restart",
        "Request an orderly restart.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "power.force_off",
        "Force power off",
        "Force a target off without relying on the operating system.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "power.force_restart",
        "Force restart",
        "Force an immediate target restart.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "power.power_cycle",
        "Power cycle",
        "Force a target off and back on.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "power.reset",
        "ATX reset",
        "Trigger a hardware reset through the out-of-band controller.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "power.nmi",
        "Send NMI",
        "Trigger a non-maskable interrupt.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "media.mount_approved_iso",
        "Mount approved ISO",
        "Mount a pre-approved virtual media image.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "media.mount_arbitrary_iso",
        "Mount arbitrary ISO",
        "Mount an operator-provided arbitrary virtual media image.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
    _capability(
        "media.eject",
        "Eject media",
        "Eject virtual media from a target.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "boot.override",
        "Boot override",
        "Set a one-time or persistent boot override.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
    _capability(
        "boot.enter_bios",
        "Enter BIOS",
        "Request boot into BIOS or setup environment.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "bios.view_settings",
        "View BIOS settings",
        "Read BIOS settings without changing them.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "bios.change_setting",
        "Change BIOS setting",
        "Modify a BIOS setting.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
    _capability(
        "firmware.update_bios",
        "Update BIOS firmware",
        "Update system BIOS firmware.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "firmware.update_bmc",
        "Update BMC firmware",
        "Update BMC firmware.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "storage.view_disk_layout",
        "View disk layout",
        "Read disk or volume layout.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "storage.wipe_disk",
        "Wipe disk",
        "Erase a disk.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "storage.repartition_disk",
        "Repartition disk",
        "Modify disk partitions.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "storage.restore_backup",
        "Restore backup",
        "Restore data from a backup.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "network.read_config",
        "Read network config",
        "Read host or BMC network configuration.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "network.change_bmc_ip",
        "Change BMC IP",
        "Modify BMC network address configuration.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
    _capability(
        "network.change_host_ip",
        "Change host IP",
        "Modify host network address configuration.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
    _capability(
        "bmc.account_list",
        "List BMC accounts",
        "Read non-secret BMC account metadata.",
        RiskLevel.MEDIUM,
    ),
    _capability(
        "bmc.rotate_password",
        "Rotate BMC password",
        "Change a BMC account password.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
    _capability(
        "bmc.reset",
        "Reset BMC",
        "Restart or reset a BMC.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
    _capability(
        "secrets.inject_reference",
        "Inject secret reference",
        "Use a scoped secret reference without revealing raw secret material.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "secrets.raw_reveal",
        "Reveal raw secret",
        "Reveal raw secret material to the requester.",
        RiskLevel.CRITICAL,
        dangerous=True,
        required_scope=("target", "session", "credential"),
    ),
    _capability(
        "runtime.noop",
        "Runtime no-op",
        "Exercise the control plane without provider side effects.",
        RiskLevel.LOW,
        required_scope=("session",),
    ),
    _capability(
        "runtime.request_clearance",
        "Request clearance",
        "Request ACT clearance without granting or executing provider actions.",
        RiskLevel.LOW,
        required_scope=("session",),
    ),
    _capability(
        "runtime.deny_clearance",
        "Deny clearance",
        "Record a clearance denial intent without granting or executing provider actions.",
        RiskLevel.LOW,
        required_scope=("session",),
    ),
    _capability(
        "runtime.run_approved_playbook",
        "Run approved playbook",
        "Run a pre-approved playbook inside explicit scope.",
        RiskLevel.HIGH,
        dangerous=True,
    ),
    _capability(
        "runtime.execute_untrusted_script",
        "Execute untrusted script",
        "Execute an untrusted script or playbook.",
        RiskLevel.CRITICAL,
        dangerous=True,
        destructive=True,
    ),
    _capability(
        "runtime.call_external_webhook",
        "Call external webhook",
        "Call an external webhook from the runtime.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
    _capability(
        "runtime.spawn_subagent",
        "Spawn subagent",
        "Create another agent or delegated runtime.",
        RiskLevel.CRITICAL,
        dangerous=True,
    ),
)

DEFAULT_CAPABILITY_REGISTRY = CapabilityRegistry(DEFAULT_CAPABILITIES)
