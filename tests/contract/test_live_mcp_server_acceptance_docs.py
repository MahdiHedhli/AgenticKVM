from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").lower()


def test_live_mcp_dependency_gate_artifacts_exist() -> None:
    required_paths = [
        "docs/mcp-sdk-dependency-review.md",
        "docs/mcp-sdk-candidate-matrix.md",
        "docs/adr/0003-live-mcp-server-boundary.md",
        "docs/mcp-live-server-acceptance.md",
        "specs/006-mcp-sdk-adapter/contracts/sdk-dependency-review.md",
        "specs/006-mcp-sdk-adapter/contracts/live-server-acceptance-gate.md",
    ]

    for relative_path in required_paths:
        assert (ROOT / relative_path).exists(), relative_path


def test_live_mcp_acceptance_gate_requires_host_conformance_path() -> None:
    gate = _read("docs/mcp-live-server-acceptance.md")

    for expected in [
        "mcp host compatibility contract",
        "mcpsdkadapter",
        "mcprouter",
        "controlplane",
        "provider adapter only if allowed",
        "not become authority",
    ]:
        assert expected in gate


def test_live_mcp_acceptance_gate_preserves_approval_and_audit() -> None:
    gate = _read("docs/mcp-live-server-acceptance.md")

    for expected in [
        "approval_required",
        "without auto-approval",
        "approval response submission",
        "one-time and session approval",
        "audit lifecycle",
        "audit failure fail-closed",
        "checkpoint-backed tail-truncation detection",
        "export/import verification",
    ]:
        assert expected in gate


def test_live_mcp_boundary_adr_keeps_real_providers_deferred() -> None:
    adr = _read("docs/adr/0003-live-mcp-server-boundary.md")

    for expected in [
        "no network listener by default",
        "real providers remain disabled by default",
        "mock-only test mode is mandatory",
        "must not call providers directly",
        "must not auto-approve",
        "credential references must remain redacted",
    ]:
        assert expected in adr


def test_roadmap_keeps_live_mcp_server_deferred() -> None:
    roadmap = _read("docs/roadmap.md")

    assert "live mcp sdk server and client integration deferred" in roadmap
    assert "keep ci mock-only" in roadmap
