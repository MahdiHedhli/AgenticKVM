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
    SQLiteAuditSink,
    create_sqlite_audit_checkpoint,
    export_sqlite_audit,
    fingerprint_parameters,
    inspect_sqlite_audit_event,
    list_sqlite_audit_events,
    mode_preset,
    verify_audit_chain,
    verify_sqlite_audit_chain,
)
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.playbooks import PlaybookRunner


def main(argv: Sequence[str] | None = None) -> int:
    """Run the AgenticKVM CLI."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        audit_sink = _audit_sink_from_args(args)
        approval_queue = _approval_queue_from_args(args, audit_sink=audit_sink)
        if args.command == "approvals":
            return _approvals(args, approval_queue)
        if args.command == "audit":
            return _audit(args)
        runtime = build_runtime(
            load_config(args.config),
            audit_sink=audit_sink,
            approval_store=approval_queue.to_approval_store() if approval_queue else None,
        )
        if args.command == "list-providers":
            _print_json(_providers_payload(runtime))
            return 0
        if args.command == "list-targets":
            _print_json(_targets_payload(runtime))
            return 0
        if args.command in {"status", "console"}:
            _print_json(
                _status_payload(
                    runtime,
                    approval_queue,
                    args.audit_path,
                    args.audit_sqlite_path,
                )
            )
            return 0
        if args.command == "playbooks":
            return _playbooks(args, runtime)
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
    parser.add_argument(
        "--audit-sqlite-path",
        help="Explicit local SQLite audit path.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-providers")
    subparsers.add_parser("list-targets")
    subparsers.add_parser("status")
    subparsers.add_parser("console")

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

    audit = subparsers.add_parser("audit")
    audit_actions = audit.add_subparsers(dest="audit_command")
    verify = audit_actions.add_parser("verify")
    verify.add_argument("--jsonl-path")
    verify.add_argument("--sqlite-path")
    list_events = audit_actions.add_parser("list")
    list_events.add_argument("--sqlite-path", required=True)
    list_events.add_argument("--limit", type=int, default=20)
    export = audit_actions.add_parser("export")
    export.add_argument("--sqlite-path", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--checkpoint-path")
    checkpoint = audit_actions.add_parser("checkpoint")
    checkpoint.add_argument("--sqlite-path", required=True)
    checkpoint.add_argument("--audit-log-id", required=True)
    checkpoint.add_argument("--output", required=True)
    inspect_event = audit_actions.add_parser("inspect")
    inspect_event.add_argument("--sqlite-path", required=True)
    inspect_group = inspect_event.add_mutually_exclusive_group(required=True)
    inspect_group.add_argument("--event-index", type=int)
    inspect_group.add_argument("--event-hash")

    playbooks = subparsers.add_parser("playbooks")
    playbook_actions = playbooks.add_subparsers(dest="playbook_command")
    playbook_actions.add_parser("list")
    dry_run = playbook_actions.add_parser("dry-run")
    dry_run.add_argument("name")
    dry_run.add_argument("--target", required=True)
    run = playbook_actions.add_parser("run")
    run.add_argument("name")
    run.add_argument("--target", required=True)
    run.add_argument("--session-id", default="playbook-session")
    run.add_argument("--requester-id", default="playbook-runner")
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


def _audit(args: argparse.Namespace) -> int:
    if args.audit_command == "verify":
        if bool(args.jsonl_path) == bool(args.sqlite_path):
            raise ValueError("audit verify requires exactly one audit path")
        if args.jsonl_path:
            payload = {
                "status": "ok" if verify_audit_chain(args.jsonl_path) else "audit_error",
                "backend": "jsonl",
                "path": args.jsonl_path,
            }
        else:
            verification = verify_sqlite_audit_chain(args.sqlite_path)
            payload = {
                "status": "ok" if verification.ok else "audit_error",
                "backend": "sqlite",
                "path": args.sqlite_path,
                "verification": verification.to_dict(),
            }
        _print_json(payload)
        return 0 if payload["status"] == "ok" else 2
    if args.audit_command == "list":
        _print_json(
            {
                "status": "ok",
                "backend": "sqlite",
                "path": args.sqlite_path,
                "events": list(list_sqlite_audit_events(args.sqlite_path, limit=args.limit)),
            }
        )
        return 0
    if args.audit_command == "export":
        checkpoint = None
        if args.checkpoint_path:
            with open(args.checkpoint_path, encoding="utf-8") as handle:
                checkpoint = json.load(handle)
        payload = export_sqlite_audit(
            args.sqlite_path,
            output_path=args.output,
            checkpoint=checkpoint,
        )
        _print_json({"status": "ok", "export": payload})
        return 0
    if args.audit_command == "checkpoint":
        checkpoint = create_sqlite_audit_checkpoint(
            args.sqlite_path,
            audit_log_id=args.audit_log_id,
        )
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(checkpoint.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        _print_json({"status": "ok", "checkpoint": checkpoint.to_dict(), "output": args.output})
        return 0
    if args.audit_command == "inspect":
        event = inspect_sqlite_audit_event(
            args.sqlite_path,
            event_index=args.event_index,
            event_hash=args.event_hash,
        )
        _print_json({"status": "ok", "backend": "sqlite", "event": event})
        return 0
    raise ValueError("unknown audit command")


def _playbooks(args: argparse.Namespace, runtime: Any) -> int:
    runner = PlaybookRunner(runtime)
    if args.playbook_command == "list":
        _print_json(runner.list_playbooks())
        return 0
    if args.playbook_command == "dry-run":
        _print_json(runner.dry_run(args.name, target=args.target))
        return 0
    if args.playbook_command == "run":
        payload = runner.run(
            args.name,
            target=args.target,
            session_id=args.session_id,
            requester_id=args.requester_id,
        )
        _print_json(payload)
        return 0 if payload["status"] == "ok" else 2
    raise ValueError("unknown playbooks command")


def _providers_payload(runtime: Any) -> dict[str, Any]:
    return {"providers": [dict(item) for item in runtime.provider_registry.list_summaries()]}


def _targets_payload(runtime: Any) -> dict[str, Any]:
    return {"targets": [dict(item) for item in runtime.target_registry.list_summaries()]}


def _status_payload(
    runtime: Any,
    approval_queue: LocalApprovalQueue | None,
    audit_path: str | None,
    audit_sqlite_path: str | None,
) -> dict[str, Any]:
    providers = [dict(item) for item in runtime.provider_registry.list_summaries()]
    targets = [dict(item) for item in runtime.target_registry.list_summaries()]
    real_provider_enabled = any(
        provider["enabled"] and provider["type"] not in {"mock"}
        for provider in providers
        if not _fixture_provider_summary(provider)
    )
    payload: dict[str, Any] = {
        "status": "ok",
        "mode": runtime.policy.mode.value,
        "providers": providers,
        "targets": targets,
        "pending_approvals": [],
        "audit": _audit_status(audit_path, audit_sqlite_path),
        "safety": {
            "live_providers_enabled_by_default": False,
            "real_provider_enabled": real_provider_enabled,
            "emergency_stop": "not_active",
            "network_listener": False,
        },
    }
    if approval_queue is not None:
        payload["pending_approvals"] = [
            record.to_summary()
            for record in approval_queue.list_records()
            if record.status.value == "pending"
        ]
        payload["approval_queue"] = {
            "path": str(approval_queue.path),
            "configured": True,
        }
    else:
        payload["approval_queue"] = {"path": None, "configured": False}
    return payload


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


def _approval_queue_from_args(
    args: argparse.Namespace,
    *,
    audit_sink: Any | None = None,
) -> LocalApprovalQueue | None:
    if not args.approval_path:
        return None
    return LocalApprovalQueue(args.approval_path, audit_sink=audit_sink)


def _audit_sink_from_args(args: argparse.Namespace) -> Any | None:
    if args.audit_path and args.audit_sqlite_path:
        raise ValueError("choose either --audit-path or --audit-sqlite-path")
    if args.audit_path:
        return LocalJSONLAuditSink(args.audit_path)
    if args.audit_sqlite_path:
        return SQLiteAuditSink(args.audit_sqlite_path)
    return None


def _audit_status(audit_path: str | None, audit_sqlite_path: str | None) -> dict[str, Any]:
    if audit_path:
        return {
            "backend": "jsonl",
            "path": audit_path,
            "configured": True,
            "hash_chain_valid": verify_audit_chain(audit_path),
        }
    if audit_sqlite_path:
        verification = verify_sqlite_audit_chain(audit_sqlite_path)
        return {
            "backend": "sqlite",
            "path": audit_sqlite_path,
            "configured": True,
            "hash_chain_valid": verification.ok,
            "verification": verification.to_dict(),
        }
    return {
        "backend": None,
        "path": None,
        "configured": False,
        "hash_chain_valid": None,
    }


def _fixture_provider_summary(provider: dict[str, Any]) -> bool:
    return bool(provider.get("executable")) and provider.get("type") in {"pikvm", "redfish"}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
