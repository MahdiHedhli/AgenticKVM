"""Live provider preflight gates.

These gates validate readiness metadata before any future live provider work.
They do not create transports, resolve credentials, or contact providers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class PreflightStatus(StrEnum):
    """Preflight result status."""

    OK = "ok"
    BLOCKED = "blocked"


OBSERVE_ONLY_PROVIDER_TYPES = frozenset({"pikvm", "redfish"})


@dataclass(frozen=True)
class LiveProviderPreflightRequest:
    """Input evidence for live-provider preflight."""

    provider_type: str
    target_id: str
    live_provider_enabled: bool
    external_config_path: str | None
    credential_ref: str | None
    audit_backend_configured: bool
    approval_transport_configured: bool
    artifact_path: str | None = None
    tls_policy_reviewed: bool = False
    timeout_policy_reviewed: bool = False
    manual_smoke_acknowledged: bool = False
    ci_mode: bool = False
    test_mode: bool = False
    committed_config_provider_enabled: bool = False
    capabilities: tuple[str, ...] = ()
    repo_root: str | None = None
    provider_id: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_type", self.provider_type.strip().lower())
        object.__setattr__(self, "capabilities", tuple(str(item) for item in self.capabilities))


@dataclass(frozen=True)
class LiveProviderPreflightResult:
    """Result of live-provider preflight."""

    status: PreflightStatus
    provider_type: str
    target_id: str
    provider_id: str | None = None
    blockers: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Return whether preflight passed."""

        return self.status == PreflightStatus.OK

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe preflight output."""

        return {
            "status": self.status.value,
            "provider_type": self.provider_type,
            "provider_id": self.provider_id,
            "target_id": self.target_id,
            "ok": self.ok,
            "blockers": list(self.blockers),
            "checks": list(self.checks),
        }


def run_live_provider_preflight(
    request: LiveProviderPreflightRequest,
) -> LiveProviderPreflightResult:
    """Validate live-provider readiness evidence."""

    blockers: list[str] = []
    checks: list[str] = []

    if request.provider_type not in OBSERVE_ONLY_PROVIDER_TYPES:
        blockers.append("unsupported live provider type")
    else:
        checks.append("provider type is observe-only candidate")

    if not request.target_id:
        blockers.append("target id is required")
    else:
        checks.append("target id provided")

    if request.ci_mode:
        blockers.append("CI mode blocks live provider preflight")
    if request.test_mode:
        blockers.append("test mode blocks live provider preflight")

    if request.committed_config_provider_enabled:
        blockers.append("committed provider config must not enable live provider")
    else:
        checks.append("committed config does not enable live provider")

    if not request.live_provider_enabled:
        blockers.append("live provider must be explicitly enabled outside defaults")
    else:
        checks.append("external live-provider enablement acknowledged")

    if not request.external_config_path:
        blockers.append("external config path is required")
    else:
        external_config_blocker = _absolute_path_blocker(
            request.external_config_path,
            "external config path",
        )
        if external_config_blocker:
            blockers.append(external_config_blocker)
        else:
            checks.append("external config path supplied")

    if not request.credential_ref:
        blockers.append("credential_ref is required")
    else:
        checks.append("credential_ref present and not resolved")

    if not request.audit_backend_configured:
        blockers.append("audit backend is required")
    else:
        checks.append("audit backend configured")

    if not request.approval_transport_configured:
        blockers.append("approval transport is required")
    else:
        checks.append("approval transport configured")

    if request.provider_type == "pikvm" and not request.artifact_path:
        blockers.append("artifact path is required for PiKVM screen/screenshot providers")
    if request.artifact_path:
        artifact_blocker = _artifact_path_blocker(request.artifact_path, request.repo_root)
        if artifact_blocker:
            blockers.append(artifact_blocker)
        else:
            checks.append("artifact path is outside repository")

    if not request.tls_policy_reviewed:
        blockers.append("TLS policy review is required")
    else:
        checks.append("TLS policy reviewed")

    if not request.timeout_policy_reviewed:
        blockers.append("timeout policy review is required")
    else:
        checks.append("timeout policy reviewed")

    if not request.manual_smoke_acknowledged:
        blockers.append("manual smoke gate must be acknowledged")
    else:
        checks.append("manual smoke gate acknowledged")

    unsafe_capabilities = [
        capability
        for capability in request.capabilities
        if not capability.startswith("observe.") and capability != "provider.status"
    ]
    if unsafe_capabilities:
        blockers.append(
            "observe-only preflight cannot include mutating capabilities: "
            + ", ".join(sorted(unsafe_capabilities))
        )
    else:
        checks.append("capability set is observe-only")

    return LiveProviderPreflightResult(
        status=PreflightStatus.BLOCKED if blockers else PreflightStatus.OK,
        provider_type=request.provider_type,
        target_id=request.target_id,
        provider_id=request.provider_id,
        blockers=tuple(blockers),
        checks=tuple(checks),
    )


def detected_ci_mode() -> bool:
    """Return whether common CI markers are present."""

    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"


def detected_test_mode() -> bool:
    """Return whether pytest appears to be executing this process."""

    return "PYTEST_CURRENT_TEST" in os.environ


def _artifact_path_blocker(artifact_path: str, repo_root: str | None) -> str | None:
    absolute_blocker = _absolute_path_blocker(artifact_path, "artifact path")
    if absolute_blocker:
        return absolute_blocker
    path = Path(artifact_path).expanduser()
    if repo_root is None:
        return None
    try:
        resolved = path.resolve()
        root = Path(repo_root).resolve()
    except OSError:
        return "artifact path cannot be resolved"
    if resolved == root or root in resolved.parents:
        return "artifact path must not point inside the repository"
    return None


def _absolute_path_blocker(path_value: str, label: str) -> str | None:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        return f"{label} must be absolute"
    return None


__all__ = [
    "LiveProviderPreflightRequest",
    "LiveProviderPreflightResult",
    "OBSERVE_ONLY_PROVIDER_TYPES",
    "PreflightStatus",
    "detected_ci_mode",
    "detected_test_mode",
    "run_live_provider_preflight",
]
