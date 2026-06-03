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
