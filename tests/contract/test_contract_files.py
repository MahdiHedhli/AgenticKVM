import json
from pathlib import Path

from agentickvm.control_plane import CAPABILITY_FAMILIES, INTERNAL_DECISIONS

ROOT = Path(__file__).resolve().parents[2]


def test_required_contract_files_exist_and_are_json() -> None:
    contracts = [
        "policy.schema.json",
        "capability-registry.schema.json",
        "approval-request.schema.json",
        "audit-event.schema.json",
    ]

    for contract in contracts:
        path = ROOT / "specs" / "002-control-plane" / "contracts" / contract
        assert path.exists(), contract
        with path.open() as handle:
            assert json.load(handle)["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_policy_schema_preserves_unknown_capability_default_deny() -> None:
    path = ROOT / "specs" / "002-control-plane" / "contracts" / "policy.schema.json"
    schema = json.loads(path.read_text())

    unknown = schema["properties"]["defaults"]["properties"]["unknown_capability"]
    decisions = schema["$defs"]["policyDecision"]["enum"]
    families = schema["$defs"]["capabilityFamily"]["enum"]

    assert unknown == {"const": "deny"}
    assert decisions == list(INTERNAL_DECISIONS)
    assert families == list(CAPABILITY_FAMILIES)


def test_policy_examples_exist_for_visible_modes() -> None:
    expected = {
        "observe.yaml",
        "assisted.yaml",
        "supervised.yaml",
        "full-control.yaml",
        "custom.example.yaml",
    }

    policy_dir = ROOT / "examples" / "policies"
    actual = {path.name for path in policy_dir.glob("*.yaml")}

    assert expected <= actual
    for path in policy_dir.glob("*.yaml"):
        text = path.read_text()
        assert "unknown_capability: deny" in text
        assert "audit: mandatory" in text
        assert "secrets: redact_by_default" in text


def test_provider_taxonomy_is_oob_only_with_inband_parking_lot() -> None:
    taxonomy = (ROOT / "docs" / "provider-taxonomy.md").read_text()

    assert "Out-Of-Band Providers" in taxonomy
    assert "AgenticKVM is out-of-band only" in taxonomy
    assert "not on the AgenticKVM roadmap" in taxonomy
    assert "Parking Lot: In-Band Remote Session Providers" in taxonomy


def test_inband_remote_session_provider_spec_is_parked_not_active() -> None:
    spec_dir = ROOT / "specs" / "007-inband-remote-session-providers"
    parking_lot = ROOT / "docs" / "parking-lot" / "inband-remote-session-providers.md"

    assert not spec_dir.exists()
    text = parking_lot.read_text()
    assert "not on the active AgenticKVM roadmap" in text
    for provider in ("RustDesk", "VNC", "RDP", "MeshCentral"):
        assert provider in text
    for forbidden in (
        "file transfer",
        "remote command execution",
        "remote access agent install",
    ):
        assert forbidden in text
