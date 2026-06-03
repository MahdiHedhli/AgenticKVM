from pathlib import Path

from agentickvm.control_plane import (
    DANGEROUS_ACTIONS,
    HARD_INVARIANTS,
    default_decision_for_unknown_capability,
)
from agentickvm.providers import MockProvider

ROOT = Path(__file__).resolve().parents[2]


def test_unknown_capabilities_are_expected_to_deny_by_design() -> None:
    assert default_decision_for_unknown_capability("unknown.capability") == "deny"


def test_required_dangerous_actions_are_documented() -> None:
    required = {
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
    }

    assert required == set(DANGEROUS_ACTIONS)


def test_full_control_hard_invariants_are_present() -> None:
    assert len(HARD_INVARIANTS) == 12
    assert any("cannot disable audit logging" in item for item in HARD_INVARIANTS)
    assert any("cannot change its own policy" in item for item in HARD_INVARIANTS)
    assert any("cannot reveal raw secrets by default" in item for item in HARD_INVARIANTS)


def test_no_real_provider_adapters_exist_in_bootstrap() -> None:
    provider_dir = ROOT / "src" / "agentickvm" / "providers"
    provider_files = {path.name for path in provider_dir.glob("*.py")}

    assert provider_files == {"__init__.py", "base.py", "mock.py"}
    assert MockProvider.is_real_hardware is False


def test_provider_contract_forbids_policy_ownership() -> None:
    contract = (
        ROOT
        / "specs"
        / "002-control-plane"
        / "contracts"
        / "provider-contract.md"
    ).read_text()

    assert "must not" in contract
    assert "decide visible control mode" in contract
    assert "MCP tools, CLI commands, API handlers, and agent workflows must not call" in contract
