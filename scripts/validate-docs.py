#!/usr/bin/env python3
"""Validate docs, specs, site files, and public safety claims."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    ".specify/memory/constitution.md",
    "README.md",
    "docs/architecture.md",
    "docs/control-plane.md",
    "docs/security-model.md",
    "docs/provider-contracts.md",
    "docs/provider-taxonomy.md",
    "docs/parking-lot/inband-remote-session-providers.md",
    "docs/github-pages.md",
    "docs/packaging.md",
    "docs/cli-smoke.md",
    "docs/linting.md",
    "docs/type-checking.md",
    "docs/coverage-policy.md",
    "docs/site-preview.md",
    "docs/release-artifacts.md",
    "docs/release-pr-review-package.md",
    "docs/release-readiness.md",
    "docs/release-checklist.md",
    "docs/sqlite-audit-hardening.md",
    "docs/approval-queue.md",
    "docs/approval-notifiers.md",
    "docs/act-clearance-client.md",
    "docs/approval-broker-v1-review.md",
    "docs/conversational-approval.md",
    "docs/mcp-elicitation.md",
    "docs/conformance-matrix.md",
    "docs/recovery-playbooks.md",
    "docs/live-provider-preflight.md",
    "docs/public-beta-risk-register.md",
    "docs/public-beta-readiness.md",
    "docs/public-beta-merge-review.md",
    "docs/public-beta-cutover-plan.md",
    "docs/releases/public-beta-0.1.0.md",
    "docs/public-beta-known-limitations.md",
    "docs/public-beta-security-statement.md",
    "docs/github-pages-enablement-checklist.md",
    "docs/maintainer-runbook.md",
    "docs/public-beta-final-review.md",
    "docs/public-beta-merge-commands.md",
    "docs/public-beta-tagging-plan.md",
    "docs/public-beta-final-handoff.md",
    "docs/roadmap.md",
    "site/index.html",
    "site/styles.css",
    "site/README.md",
    "scripts/check-package.py",
    "scripts/build-package.py",
    "scripts/smoke-cli.py",
    "scripts/lint-sanity.py",
    "scripts/type-sanity.py",
    "scripts/validate-docs.py",
    "scripts/check-site.py",
    "scripts/generate-release-manifest.py",
    "scripts/check-public-beta.py",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/security_report.md",
    ".github/pull_request_template.md",
    "specs/002-control-plane/spec.md",
    "specs/002-control-plane/contracts/capability-registry.schema.json",
    "specs/002-control-plane/contracts/policy.schema.json",
    "specs/002-control-plane/contracts/provider-contract.md",
    "specs/003-real-provider-readiness/spec.md",
    "specs/006-mcp-sdk-adapter/spec.md",
    "specs/006-mcp-sdk-adapter/contracts/elicitation-capability-detection.md",
    "specs/008-production-audit-store/spec.md",
    "specs/008-production-audit-store/contracts/sqlite-audit-backend-v1.md",
    "specs/009-approval-broker-v1/spec.md",
    "specs/009-approval-broker-v1/contracts/signed-grant-contract.md",
    "specs/009-approval-broker-v1/contracts/approval-channel-policy.md",
    "specs/009-approval-broker-v1/contracts/mcp-approval-tools.md",
    "specs/011-act-clearance-client/spec.md",
    "specs/011-act-clearance-client/contracts/clearance-request.md",
    "specs/011-act-clearance-client/contracts/clearance-response.md",
    "specs/011-act-clearance-client/contracts/act-client-boundary.md",
)

SAFETY_EXPECTATIONS = {
    "docs/security-model.md": (
        "fail closed",
        "must not use real hardware",
        "Secrets",
        "Provider and target registries",
        "clearance",
        "Audit",
    ),
    "docs/control-plane.md": (
        "Provider registry",
        "Target registry",
        "policy",
        "approval",
        "audit",
        "fail closed",
    ),
    "docs/provider-contracts.md": (
        "Mock First",
        "Provider Must Not Decide",
        "Readiness Gates",
        "disabled placeholders",
    ),
    "docs/live-provider-preflight.md": (
        "CI mode",
        "test mode",
        "credential_ref",
        "artifact path",
        "observe-only",
    ),
    "docs/public-beta-readiness.md": (
        "killer demo",
        "live-provider preflight",
        "SDK trial dependency",
        "human",
    ),
    "docs/public-beta-security-statement.md": (
        "mock-only",
        "credential references",
        "Live PiKVM",
        "Vulnerability Reporting",
    ),
}

PUBLIC_CLAIM_FILES = (
    "README.md",
    "site/index.html",
)

FORBIDDEN_PUBLIC_CLAIMS = (
    "production ready",
    "fully supports live pikvm",
    "fully supports live redfish",
    "supports rdp today",
    "supports vnc today",
    "supports rustdesk today",
    "supports meshcentral today",
    "autonomous production recovery",
    "zero risk",
    "mcp==1.27.2",
)

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


class ValidationFailure(RuntimeError):
    """Raised when documentation validation fails."""


def main() -> int:
    try:
        _validate_required_files()
        _validate_readme_links()
        _validate_safety_language()
        _validate_public_claims()
        _validate_oob_only_roadmap()
        _validate_mcp_approval_tools()
        _validate_act_clearance_boundary()
        _validate_donor_port_targets()
        _validate_public_beta_deferred()
        _validate_local_markdown_links()
    except Exception as exc:
        print(f"docs validation failed: {exc}", file=sys.stderr)
        return 1
    print("docs validation passed")
    return 0


def _validate_required_files() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        raise ValidationFailure(f"missing required files: {', '.join(missing)}")


def _validate_readme_links() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for expected in (
        ".specify/memory/constitution.md",
        "specs/002-control-plane/",
        "docs/",
        "site/",
        "tests/",
    ):
        if expected not in text:
            raise ValidationFailure(f"README missing repository map entry {expected}")


def _validate_safety_language() -> None:
    for relative, snippets in SAFETY_EXPECTATIONS.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        lowered = text.lower()
        for snippet in snippets:
            if snippet.lower() not in lowered:
                raise ValidationFailure(f"{relative} missing safety language {snippet!r}")


def _validate_public_claims() -> None:
    for relative in PUBLIC_CLAIM_FILES:
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PUBLIC_CLAIMS:
            if phrase in text:
                raise ValidationFailure(f"{relative} contains forbidden claim {phrase!r}")


def _validate_oob_only_roadmap() -> None:
    roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8").lower()
    for phrase in (
        "future in-band",
        "future remote session",
        "future session-level",
        "roadmap-only",
    ):
        if phrase in roadmap:
            raise ValidationFailure(f"roadmap still contains active parked-scope phrase {phrase!r}")
    for phrase in ("rustdesk", "vnc", "rdp", "meshcentral"):
        if phrase in roadmap and "parked scope" not in roadmap:
            raise ValidationFailure(f"roadmap mentions {phrase!r} outside parking context")
    parking = (ROOT / "docs" / "parking-lot" / "inband-remote-session-providers.md").read_text(
        encoding="utf-8"
    )
    if "not on the active AgenticKVM roadmap" not in parking:
        raise ValidationFailure("parking-lot doc must mark in-band providers as inactive")


def _validate_mcp_approval_tools() -> None:
    registry = (ROOT / "src" / "agentickvm" / "mcp" / "registry.py").read_text(
        encoding="utf-8"
    )
    if 'tool_name="request_clearance"' not in registry:
        raise ValidationFailure("MCP registry missing request_clearance tool")
    if 'tool_name="deny_clearance"' not in registry:
        raise ValidationFailure("MCP registry missing deny_clearance tool")
    forbidden = (
        'tool_name="grant_approval"',
        'tool_name="approve"',
        'tool_name="approve_approval"',
        'tool_name="sign_approval"',
        'tool_name="grant_clearance"',
        'tool_name="approve_clearance"',
        'tool_name="clear_clearance"',
        'tool_name="sign_clearance"',
    )
    for snippet in forbidden:
        if snippet in registry:
            raise ValidationFailure(f"MCP registry contains forbidden approval tool {snippet}")


def _validate_act_clearance_boundary() -> None:
    act_doc = (ROOT / "docs" / "act-clearance-client.md").read_text(encoding="utf-8")
    required = (
        "ACT owns",
        "AgenticKVM consumes ACT clearance",
        "client-side mirror",
        "must not author a competing clearance wire contract",
        "must never expose grant, approve, clear, sign, or trust-signer tools",
    )
    for snippet in required:
        if snippet not in act_doc:
            raise ValidationFailure(f"ACT clearance doc missing {snippet!r}")
    for relative in (
        "specs/011-act-clearance-client/contracts/clearance-request.md",
        "specs/011-act-clearance-client/contracts/clearance-response.md",
        "specs/011-act-clearance-client/contracts/act-client-boundary.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        if "Canonical source: Agentic Control Tower" not in text:
            raise ValidationFailure(f"{relative} must name ACT as canonical source")
        if "not an AgenticKVM-owned" not in text:
            raise ValidationFailure(f"{relative} must reject AgenticKVM-owned contract framing")
    source_files = (
        ROOT / "src" / "agentickvm" / "control_plane" / "clearance.py",
        ROOT / "src" / "agentickvm" / "control_plane" / "act_client.py",
    )
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        if "ACT is the source of truth" not in text:
            raise ValidationFailure(f"{path.relative_to(ROOT)} missing ACT source-of-truth header")
        if "not an AgenticKVM-owned wire contract" not in text:
            raise ValidationFailure(f"{path.relative_to(ROOT)} missing mirror-contract warning")


def _validate_donor_port_targets() -> None:
    donor = (ROOT / "docs" / "donor-spike-inventory.md").read_text(encoding="utf-8")
    for snippet in (
        "PiKVM Cert-Pinning Preflight",
        "HID Text Redaction With Explicit Full-Capture Opt-In",
        "Real PiKVM Tool Surface And Screenshot Mouse Calibration",
        "Port target",
    ):
        if snippet not in donor:
            raise ValidationFailure(f"donor spike inventory missing port target {snippet!r}")


def _validate_public_beta_deferred() -> None:
    for relative in (
        "README.md",
        "docs/roadmap.md",
        "docs/public-beta-readiness.md",
        "docs/releases/public-beta-0.1.0.md",
        "site/index.html",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        if "killer demo" not in text:
            raise ValidationFailure(f"{relative} must name the killer demo launch gate")
        if "public beta is deferred" not in text:
            raise ValidationFailure(f"{relative} must state that public beta is deferred")


def _validate_local_markdown_links() -> None:
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    for markdown in markdown_files:
        for target in MARKDOWN_LINK_RE.findall(markdown.read_text(encoding="utf-8")):
            if _skip_link(target):
                continue
            target_path = (markdown.parent / target.split("#", 1)[0]).resolve()
            if not target_path.exists():
                raise ValidationFailure(
                    f"{markdown.relative_to(ROOT)} has broken local link {target!r}"
                )


def _skip_link(target: str) -> bool:
    if target.startswith(("#", "http://", "https://", "mailto:")):
        return True
    if not target.split("#", 1)[0]:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
