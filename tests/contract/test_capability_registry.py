import json
from pathlib import Path

from agentickvm.control_plane import (
    CAPABILITY_FAMILIES,
    DANGEROUS_ACTIONS,
    DEFAULT_CAPABILITY_REGISTRY,
)

ROOT = Path(__file__).resolve().parents[2]


def test_default_capability_registry_covers_required_families() -> None:
    assert DEFAULT_CAPABILITY_REGISTRY.families() == frozenset(CAPABILITY_FAMILIES)


def test_default_capability_registry_ids_match_schema_pattern() -> None:
    schema_path = (
        ROOT
        / "specs"
        / "002-control-plane"
        / "contracts"
        / "capability-registry.schema.json"
    )
    schema = json.loads(schema_path.read_text())
    allowed_families = set(schema["$defs"]["capabilityFamily"]["enum"])

    for capability in DEFAULT_CAPABILITY_REGISTRY.capabilities.values():
        assert capability.family in allowed_families
        assert capability.id == f"{capability.family}.{capability.action}"
        assert capability.risk.value in {"low", "medium", "high", "critical"}


def test_registry_marks_required_dangerous_action_examples() -> None:
    registry = DEFAULT_CAPABILITY_REGISTRY

    dangerous_examples = {
        "force power actions": "power.force_off",
        "NMI": "power.nmi",
        "BMC reset": "bmc.reset",
        "arbitrary ISO mount": "media.mount_arbitrary_iso",
        "boot override": "boot.override",
        "BIOS changes": "bios.change_setting",
        "firmware updates": "firmware.update_bmc",
        "network/BMC IP changes": "network.change_bmc_ip",
        "BMC credential changes": "bmc.rotate_password",
        "disk format/wipe/repartition": "storage.wipe_disk",
        "backup restore": "storage.restore_backup",
        "raw secret reveal": "secrets.raw_reveal",
        "untrusted script/playbook execution": "runtime.execute_untrusted_script",
        "external webhook calls": "runtime.call_external_webhook",
        "subagent spawning": "runtime.spawn_subagent",
    }

    assert set(dangerous_examples) <= set(DANGEROUS_ACTIONS)
    for capability_id in dangerous_examples.values():
        assert registry.require(capability_id).dangerous is True
