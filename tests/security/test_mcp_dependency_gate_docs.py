from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").lower()


def test_dependency_review_blocks_unknown_safety_critical_facts() -> None:
    review = _read("docs/mcp-sdk-dependency-review.md")

    for expected in [
        "unknown",
        "cannot be selected",
        "authority routing",
        "provider bypass",
        "secret handling",
        "ci isolation",
    ]:
        assert expected in review


def test_dependency_review_requires_no_secret_or_raw_arg_logging() -> None:
    review = _read("docs/mcp-sdk-dependency-review.md")

    for expected in [
        "credential refs",
        "screenshots",
        "raw provider payloads",
        "raw tool arguments",
        "avoid logging",
    ]:
        assert expected in review


def test_candidate_matrix_does_not_select_dependency() -> None:
    matrix = _read("docs/mcp-sdk-candidate-matrix.md")

    assert "no dependency is selected" in matrix
    assert "candidate for offline trial, not selected" in matrix
    assert "do not add dependency in this lane" in matrix


def test_sdk_dependency_contract_rejects_provider_bypass_and_live_ci() -> None:
    contract = _read(
        "specs/006-mcp-sdk-adapter/contracts/sdk-dependency-review.md"
    )

    for expected in [
        "requires provider calls outside `controlplane`",
        "requires real providers in ci",
        "requires live network access for basic tests",
        "requires raw credentials",
        "opens public listeners by default",
        "cannot run mock-only",
    ]:
        assert expected in contract


def test_live_server_acceptance_includes_audit_store_gate() -> None:
    acceptance = _read("docs/mcp-live-server-acceptance.md")

    for expected in [
        "audit-store gate",
        "audit failure behavior",
        "provider execution and provider error audit events",
        "artifact metadata audit events",
        "checkpoint-backed tail-truncation detection",
        "no raw screenshots",
        "no raw secrets",
    ]:
        assert expected in acceptance
