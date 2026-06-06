"""Safe recovery playbook framework.

Playbooks are provider-neutral workflows that execute only through the
existing MCP router and ControlPlane. They do not call providers directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from agentickvm.config import ConfigRuntime
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest


class PlaybookStatus(StrEnum):
    """Playbook execution status."""

    OK = "ok"
    DRY_RUN = "dry_run"
    STOPPED = "stopped"
    VALIDATION_ERROR = "validation_error"


@dataclass(frozen=True)
class PlaybookStep:
    """One MCP tool step in a playbook."""

    name: str
    tool_name: str
    description: str
    params: Mapping[str, Any] = field(default_factory=dict)
    approval_checkpoint: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("playbook step name is required")
        if not self.tool_name:
            raise ValueError("playbook step tool_name is required")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe step dictionary."""

        return _json_safe(
            {
                "name": self.name,
                "tool_name": self.tool_name,
                "description": self.description,
                "params": dict(self.params),
                "approval_checkpoint": self.approval_checkpoint,
            }
        )


@dataclass(frozen=True)
class PlaybookDefinition:
    """Safe recovery playbook metadata and ordered steps."""

    name: str
    description: str
    required_capabilities: tuple[str, ...]
    risk_tier: str
    steps: tuple[PlaybookStep, ...]
    rollback_notes: str = "No provider mutation is performed by this playbook."

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("playbook name is required")
        if not self.steps:
            raise ValueError("playbook requires at least one step")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe playbook definition."""

        return _json_safe(
            {
                "name": self.name,
                "description": self.description,
                "required_capabilities": list(self.required_capabilities),
                "risk_tier": self.risk_tier,
                "dry_run_supported": True,
                "steps": [step.to_dict() for step in self.steps],
                "rollback_notes": self.rollback_notes,
            }
        )


class PlaybookRegistry:
    """Explicit playbook registry."""

    def __init__(self, playbooks: Iterable[PlaybookDefinition]) -> None:
        resolved = tuple(playbooks)
        self._playbooks = {playbook.name: playbook for playbook in resolved}
        if len(self._playbooks) != len(resolved):
            raise ValueError("duplicate playbook name")

    def list(self) -> tuple[PlaybookDefinition, ...]:
        """Return registered playbooks sorted by name."""

        return tuple(self._playbooks[name] for name in sorted(self._playbooks))

    def get(self, name: str) -> PlaybookDefinition | None:
        """Return a playbook or None."""

        return self._playbooks.get(name)

    def require(self, name: str) -> PlaybookDefinition:
        """Return a playbook or fail closed."""

        playbook = self.get(name)
        if playbook is None:
            raise ValueError(f"Unknown playbook: {name}")
        return playbook


DEFAULT_PLAYBOOK_REGISTRY = PlaybookRegistry(
    (
        PlaybookDefinition(
            name="observe-target-health",
            description="Collect basic status and power-state evidence.",
            required_capabilities=("observe.status", "observe.power_state"),
            risk_tier="low",
            steps=(
                PlaybookStep(
                    name="status",
                    tool_name="get_status",
                    description="Read provider-neutral target status.",
                ),
                PlaybookStep(
                    name="power-state",
                    tool_name="get_power_state",
                    description="Read target power state.",
                ),
            ),
        ),
        PlaybookDefinition(
            name="capture-screen-evidence",
            description="Capture screen metadata through the observe path.",
            required_capabilities=("observe.screenshot",),
            risk_tier="medium",
            steps=(
                PlaybookStep(
                    name="screen",
                    tool_name="observe_screen",
                    description="Read screen or screenshot metadata.",
                ),
            ),
        ),
        PlaybookDefinition(
            name="inspect-boot-status",
            description="Collect safe boot-status evidence.",
            required_capabilities=("observe.boot_status",),
            risk_tier="low",
            steps=(
                PlaybookStep(
                    name="boot-status",
                    tool_name="get_boot_status",
                    description="Read boot status.",
                ),
            ),
        ),
        PlaybookDefinition(
            name="collect-pre-recovery-evidence",
            description="Collect status, power, boot, and screen evidence before recovery.",
            required_capabilities=(
                "observe.status",
                "observe.power_state",
                "observe.boot_status",
                "observe.screenshot",
            ),
            risk_tier="medium",
            steps=(
                PlaybookStep("status", "get_status", "Read target status."),
                PlaybookStep("power-state", "get_power_state", "Read power state."),
                PlaybookStep("boot-status", "get_boot_status", "Read boot status."),
                PlaybookStep("screen", "observe_screen", "Read screen metadata."),
            ),
        ),
        PlaybookDefinition(
            name="wait-for-login-prompt",
            description="Mock-safe loop placeholder for observing login prompt evidence.",
            required_capabilities=("observe.screenshot",),
            risk_tier="medium",
            steps=(
                PlaybookStep(
                    name="screen-check",
                    tool_name="observe_screen",
                    description="Read screen metadata for a prompt-like fixture.",
                    params={"expected": "login_prompt"},
                ),
            ),
        ),
    )
)


class PlaybookRunner:
    """Run playbooks through MCPRouter and ControlPlane only."""

    def __init__(
        self,
        runtime: ConfigRuntime,
        *,
        registry: PlaybookRegistry = DEFAULT_PLAYBOOK_REGISTRY,
    ) -> None:
        self.runtime = runtime
        self.registry = registry

    def list_playbooks(self) -> dict[str, Any]:
        """Return playbook summaries."""

        return _json_safe(
            {
                "status": PlaybookStatus.OK.value,
                "playbooks": [playbook.to_dict() for playbook in self.registry.list()],
            }
        )

    def dry_run(self, name: str, *, target: str) -> dict[str, Any]:
        """Return the planned steps without execution."""

        playbook = self.registry.require(name)
        return _json_safe(
            {
                "status": PlaybookStatus.DRY_RUN.value,
                "playbook": playbook.to_dict(),
                "target": target,
                "would_execute": False,
            }
        )

    def run(
        self,
        name: str,
        *,
        target: str,
        session_id: str = "playbook-session",
        requester_id: str = "playbook-runner",
    ) -> dict[str, Any]:
        """Run a playbook against one target through the control plane."""

        playbook = self.registry.require(name)
        router = MCPRouter(
            provider_registry=self.runtime.provider_registry,
            target_registry=self.runtime.target_registry,
            policy=self.runtime.policy,
            audit_sink=self.runtime.audit_sink,
            approval_store=self.runtime.approval_store,
        )
        results: list[dict[str, Any]] = []
        for step in playbook.steps:
            result = router.handle_tool_request(
                MCPToolRequest(
                    tool_name=step.tool_name,
                    target=target,
                    session_id=session_id,
                    requester_id=requester_id,
                    params=step.params,
                    correlation_id=f"playbook:{playbook.name}:{step.name}",
                )
            )
            payload = result.to_dict()
            results.append({"step": step.to_dict(), "result": payload})
            if result.status != MCPResultStatus.OK:
                return _json_safe(
                    {
                        "status": PlaybookStatus.STOPPED.value,
                        "playbook": playbook.name,
                        "target": target,
                        "reason": result.reason,
                        "stop_status": result.status.value,
                        "results": results,
                    }
                )
        return _json_safe(
            {
                "status": PlaybookStatus.OK.value,
                "playbook": playbook.name,
                "target": target,
                "results": results,
            }
        )


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


__all__ = [
    "DEFAULT_PLAYBOOK_REGISTRY",
    "PlaybookDefinition",
    "PlaybookRegistry",
    "PlaybookRunner",
    "PlaybookStatus",
    "PlaybookStep",
]
