#!/usr/bin/env python3
"""Run lightweight type and model sanity checks."""

from __future__ import annotations

import importlib
import json
import sys
import tomllib
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MODULES = (
    "agentickvm",
    "agentickvm.cli",
    "agentickvm.config.loader",
    "agentickvm.control_plane.engine",
    "agentickvm.mcp.router",
    "agentickvm.mcp_sdk.adapter",
    "agentickvm.mcp_sdk.host",
    "agentickvm.providers.base",
    "agentickvm.providers.mock",
    "agentickvm.providers.pikvm",
    "agentickvm.providers.redfish",
    "agentickvm.providers.placeholders",
)

DATACLASS_CONTRACTS = (
    ("agentickvm.control_plane.engine", "CapabilityRequest"),
    ("agentickvm.control_plane.engine", "ControlPlaneResult"),
    ("agentickvm.mcp.models", "MCPToolRequest"),
    ("agentickvm.mcp.models", "MCPToolResult"),
    ("agentickvm.mcp_sdk.models", "MCPSDKToolCall"),
    ("agentickvm.mcp_sdk.host_models", "HostToolCall"),
    ("agentickvm.mcp_sdk.host_models", "HostToolResult"),
    ("agentickvm.mcp_sdk.host_models", "HostError"),
    ("agentickvm.mcp_sdk.host_models", "HostToolSchema"),
    ("agentickvm.providers.base", "ProviderActionRequest"),
    ("agentickvm.providers.base", "ProviderActionResult"),
    ("agentickvm.providers.base", "ProviderStatus"),
)


class TypeSanityFailure(RuntimeError):
    """Raised when type sanity checks fail."""


def main() -> int:
    try:
        _check_project_metadata()
        imported = _check_imports()
        dataclasses_checked = _check_dataclass_annotations()
        json_shapes = _check_json_safe_models()
        _check_trial_sdk_not_imported()
    except Exception as exc:
        print(f"type sanity failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "ok",
                "imported_modules": imported,
                "dataclasses_checked": dataclasses_checked,
                "json_shapes_checked": json_shapes,
                "sdk_trial_dependency_imported": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _check_project_metadata() -> None:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = payload.get("project", {}).get("dependencies", [])
    if any("mcp==1.27.2" in str(dependency).lower() for dependency in dependencies):
        raise TypeSanityFailure("trial MCP SDK dependency must not be present")


def _check_imports() -> int:
    count = 0
    for module_name in MODULES:
        importlib.import_module(module_name)
        count += 1
    return count


def _check_dataclass_annotations() -> int:
    count = 0
    for module_name, class_name in DATACLASS_CONTRACTS:
        cls = getattr(importlib.import_module(module_name), class_name)
        if not is_dataclass(cls):
            raise TypeSanityFailure(f"{module_name}.{class_name} must be a dataclass")
        annotations = getattr(cls, "__annotations__", {})
        missing = [field.name for field in fields(cls) if field.name not in annotations]
        if missing:
            raise TypeSanityFailure(
                f"{module_name}.{class_name} missing annotations: {', '.join(missing)}"
            )
        count += 1
    return count


def _check_json_safe_models() -> int:
    from agentickvm.mcp.models import MCPResultStatus, MCPToolResult
    from agentickvm.mcp_sdk.host_models import (
        HostError,
        HostResultStatus,
        HostToolResult,
        HostToolSchema,
    )
    from agentickvm.providers.base import ProviderActionResult

    payloads: list[dict[str, Any]] = [
        MCPToolResult(
            status=MCPResultStatus.OK,
            tool_name="get_status",
            capability="observe.status",
            target="mock-host",
            provider="mock",
            reason="ok",
        ).to_dict(),
        HostToolResult(
            status=HostResultStatus.DENIED,
            tool_name="reveal_secret",
            capability="secrets.raw_reveal",
            target="mock-host",
            provider="mock",
            reason="secret token must be redacted",
            data={"api_token": "value"},
        ).to_dict(),
        HostError(
            status=HostResultStatus.VALIDATION_ERROR,
            reason="bad request",
            details={"password": "value"},
        ).to_dict(),
        HostToolSchema(
            tool_name="get_status",
            capability="observe.status",
            description="status",
            dangerous=False,
            input_schema={"type": "object", "properties": {"target": {"type": "string"}}},
        ).to_dict(),
        ProviderActionResult(
            ok=True,
            provider_id="mock",
            provider_type="mock",
            capability="observe.status",
            action="status",
            target_id="mock-host",
            performed_on_hardware=False,
            message="ok",
            data={"password": "value"},
        ).normalized(),
    ]
    for payload in payloads:
        json.loads(json.dumps(payload, sort_keys=True))
        if "value" in json.dumps(payload):
            raise TypeSanityFailure("JSON-safe sample leaked an unredacted secret value")
    return len(payloads)


def _check_trial_sdk_not_imported() -> None:
    if "mcp" in sys.modules:
        raise TypeSanityFailure("trial MCP SDK module was imported")


if __name__ == "__main__":
    raise SystemExit(main())
