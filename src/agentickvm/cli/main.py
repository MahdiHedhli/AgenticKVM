"""Safe mock-only CLI adapter."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from agentickvm.config import build_runtime, load_config
from agentickvm.control_plane import (
    ApprovalGrantScope,
    LocalApprovalQueue,
    LocalJSONLAuditSink,
    fingerprint_parameters,
    mode_preset,
)
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest


def main(argv: Sequence[str] | None = None) -> int:
    """Run the AgenticKVM CLI."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        approval_queue = _approval_queue_from_args(args)
        if args.command == "approvals":
            return _approvals(args, approval_queue)
        runtime = build_runtime(
            load_config(args.config),
            audit_sink=LocalJSONLAuditSink(args.audit_path) if args.audit_path else None,
            approval_store=approval_queue.to_approval_store() if approval_queue else None,
        )
        if args.command == "list-providers":
            _print_json(_providers_payload(runtime))
            return 0
        if args.command == "list-targets":
            _print_json(_targets_payload(runtime))
            return 0
        if args.command == "call":
            return _call(args, runtime, approval_queue)
    except Exception as exc:  # noqa: BLE001 - CLI must return structured failures.
        _print_json({"status": "validation_error", "reason": str(exc)})
        return 2

    parser.print_help(sys.stderr)
    return 2


def _call(
    args: argparse.Namespace,
    runtime: Any,
    approval_queue: LocalApprovalQueue | None,
) -> int:
    policy = runtime.policy
    if args.mode is not None:
        policy = mode_preset(args.mode)
    params = _params_from_cli(args.param)
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=policy,
        audit_sink=runtime.audit_sink,
        approval_store=runtime.approval_store,
    )
    result = router.handle_tool_request(
        MCPToolRequest(
            tool_name=args.tool,
            target=args.target,
            session_id=args.session_id,
            requester_id=args.requester_id,
            provider=args.provider,
            requested_mode=args.mode,
            params=params,
            correlation_id=args.correlation_id,
        )
    )
    payload = result.to_dict()
    if approval_queue is not None and result.status == MCPResultStatus.APPROVAL_REQUIRED:
        queued = approval_queue.enqueue_mcp_result(payload)
        payload["approval_queue"] = {
            "path": str(approval_queue.path),
            "approval_id": queued.id,
            "status": queued.status.value,
        }
    elif (
        approval_queue is not None
        and result.status in {MCPResultStatus.OK, MCPResultStatus.PROVIDER_ERROR}
        and result.capability is not None
    ):
        consumed = approval_queue.mark_matching_consumed(
            capability_id=result.capability,
            session_id=args.session_id,
            target_id=args.target,
            provider_id=result.provider,
            params_fingerprint=fingerprint_parameters(params),
        )
        if consumed is not None:
            payload["approval_queue"] = {
                "path": str(approval_queue.path),
                "approval_id": consumed.id,
                "status": consumed.status.value,
            }
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
    parser.add_argument(
        "--approval-path",
        help="Explicit local approval queue JSON path.",
    )
    parser.add_argument(
        "--audit-path",
        help="Explicit local audit JSONL path.",
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

    approvals = subparsers.add_parser("approvals")
    approval_actions = approvals.add_subparsers(dest="approval_command")
    approval_actions.add_parser("list")
    show = approval_actions.add_parser("show")
    show.add_argument("approval_id")
    approve = approval_actions.add_parser("approve")
    approve.add_argument("approval_id")
    approve.add_argument("--operator-id", required=True)
    approve.add_argument(
        "--scope",
        choices=[scope.value for scope in ApprovalGrantScope],
        default=ApprovalGrantScope.ONE_TIME.value,
    )
    approve.add_argument("--reason")
    deny = approval_actions.add_parser("deny")
    deny.add_argument("approval_id")
    deny.add_argument("--operator-id", required=True)
    deny.add_argument("--reason")
    expire = approval_actions.add_parser("expire")
    expire.add_argument("approval_id")
    expire.add_argument("--operator-id", required=True)
    expire.add_argument("--reason")
    return parser


def _approvals(
    args: argparse.Namespace,
    approval_queue: LocalApprovalQueue | None,
) -> int:
    if approval_queue is None:
        raise ValueError("approvals commands require --approval-path")
    if args.approval_command == "list":
        _print_json(
            {
                "status": "ok",
                "approvals": [
                    record.to_summary() for record in approval_queue.list_records()
                ],
            }
        )
        return 0
    if args.approval_command == "show":
        _print_json({"status": "ok", "approval": approval_queue.get(args.approval_id).to_dict()})
        return 0
    if args.approval_command == "approve":
        record = approval_queue.approve(
            args.approval_id,
            operator_id=args.operator_id,
            scope=ApprovalGrantScope(args.scope),
            reason=args.reason,
        )
        _print_json({"status": "approval_granted", "approval": record.to_summary()})
        return 0
    if args.approval_command == "deny":
        record = approval_queue.deny(
            args.approval_id,
            operator_id=args.operator_id,
            reason=args.reason,
        )
        _print_json({"status": "approval_denied", "approval": record.to_summary()})
        return 0
    if args.approval_command == "expire":
        record = approval_queue.expire(
            args.approval_id,
            operator_id=args.operator_id,
            reason=args.reason,
        )
        _print_json({"status": "approval_expired", "approval": record.to_summary()})
        return 0
    raise ValueError("unknown approvals command")


def _providers_payload(runtime: Any) -> dict[str, Any]:
    return {"providers": [dict(item) for item in runtime.provider_registry.list_summaries()]}


def _targets_payload(runtime: Any) -> dict[str, Any]:
    return {"targets": [dict(item) for item in runtime.target_registry.list_summaries()]}


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


def _approval_queue_from_args(args: argparse.Namespace) -> LocalApprovalQueue | None:
    if not args.approval_path:
        return None
    return LocalApprovalQueue(args.approval_path, audit_path=args.audit_path)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
