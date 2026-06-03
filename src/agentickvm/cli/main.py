"""Safe mock-only CLI adapter."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from agentickvm.config import build_runtime, load_config
from agentickvm.control_plane import mode_preset
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest


def main(argv: Sequence[str] | None = None) -> int:
    """Run the AgenticKVM CLI."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        runtime = build_runtime(load_config(args.config))
        if args.command == "list-providers":
            _print_json(_providers_payload(runtime))
            return 0
        if args.command == "list-targets":
            _print_json(_targets_payload(runtime))
            return 0
        if args.command == "call":
            return _call(args, runtime)
    except Exception as exc:  # noqa: BLE001 - CLI must return structured failures.
        _print_json({"status": "validation_error", "reason": str(exc)})
        return 2

    parser.print_help(sys.stderr)
    return 2


def _call(args: argparse.Namespace, runtime: Any) -> int:
    policy = runtime.policy
    if args.mode is not None:
        policy = mode_preset(args.mode)
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=policy,
        audit_sink=runtime.audit_sink,
    )
    result = router.handle_tool_request(
        MCPToolRequest(
            tool_name=args.tool,
            target=args.target,
            session_id=args.session_id,
            requester_id=args.requester_id,
            provider=args.provider,
            requested_mode=args.mode,
            params=_params_from_cli(args.param),
            correlation_id=args.correlation_id,
        )
    )
    payload = result.to_dict()
    _print_json(payload)
    if result.status in {
        MCPResultStatus.VALIDATION_ERROR,
        MCPResultStatus.PROVIDER_ERROR,
        MCPResultStatus.POLICY_ERROR,
    }:
        return 2
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentickvm")
    parser.add_argument(
        "--config",
        help="Explicit config path. Defaults to the built-in safe mock config.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-providers")
    subparsers.add_parser("list-targets")

    call = subparsers.add_parser("call")
    call.add_argument("--target", required=True)
    call.add_argument("--tool", required=True)
    call.add_argument("--provider")
    call.add_argument("--mode")
    call.add_argument("--session-id", default="cli-session")
    call.add_argument("--requester-id", default="cli")
    call.add_argument("--correlation-id")
    call.add_argument(
        "--param",
        action="append",
        default=[],
        help="Safe key=value parameter. May be repeated.",
    )
    return parser


def _providers_payload(runtime: Any) -> dict[str, Any]:
    return {
        "providers": [
            {
                "id": provider.provider_id,
                "type": provider.provider_type,
                "enabled": provider.enabled,
                "executable": provider.enabled and provider.provider is not None,
                "description": provider.description,
            }
            for provider in runtime.provider_registry.list()
        ]
    }


def _targets_payload(runtime: Any) -> dict[str, Any]:
    return {
        "targets": [
            {
                "id": target.target_id,
                "provider": target.provider_id,
                "enabled": target.enabled,
                "name": target.name,
                "environment": target.environment,
                "labels": list(target.labels),
                "risk_tier": target.risk_tier,
                "allowed_modes": [mode.value for mode in sorted(target.allowed_modes)],
            }
            for target in runtime.target_registry.list()
        ]
    }


def _params_from_cli(values: Sequence[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"CLI params must use key=value: {value}")
        key, item = value.split("=", 1)
        if not key:
            raise ValueError("CLI param key cannot be empty")
        params[key] = item
    return params


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
