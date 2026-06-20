"""Safe mock-only CLI adapter."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentickvm.config import build_runtime, load_config
from agentickvm.control_plane import (
    ApprovalCacheError,
    ApprovalChannel,
    ApprovalGrantScope,
    GrantPayload,
    HMACDevelopmentSigner,
    LocalApprovalQueue,
    LocalJSONLAuditSink,
    SignedApprovalCache,
    SQLiteAuditSink,
    create_sqlite_audit_checkpoint,
    export_sqlite_audit,
    inspect_sqlite_audit_event,
    list_sqlite_audit_events,
    mode_preset,
    resolve_auth_channel,
    verify_audit_chain,
    verify_sqlite_audit_chain,
)
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.playbooks import PlaybookRunner
from agentickvm.providers import (
    LiveProviderPreflightRequest,
    detected_ci_mode,
    detected_test_mode,
    run_live_provider_preflight,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the AgenticKVM CLI."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            return _audit(args)
        if args.command == "providers":
            return _providers(args)
        audit_sink = _audit_sink_from_args(args)
        approval_queue = _approval_queue_from_args(args, audit_sink=audit_sink)
        if args.command == "approvals":
            return _approvals(args, approval_queue)
        runtime = build_runtime(
            load_config(args.config),
            audit_sink=audit_sink,
            approval_store=None,
        )
        # CLI --auth-channel overrides the configured channel; otherwise use the
        # config selection (default mobile_signed / ACT).
        auth_selection = resolve_auth_channel(
            args.auth_channel
            if getattr(args, "auth_channel", None)
            else runtime.config.auth_channel
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
                    auth_selection,
                )
            )
            return 0
        if args.command == "playbooks":
            return _playbooks(args, runtime)
        if args.command == "call":
            return _call(args, runtime, approval_queue, auth_selection)
    except Exception as exc:  # noqa: BLE001 - CLI must return structured failures.
        _print_json({"status": "validation_error", "reason": str(exc)})
        return 2

    parser.print_help(sys.stderr)
    return 2


def _call(
    args: argparse.Namespace,
    runtime: Any,
    approval_queue: LocalApprovalQueue | None,
    auth_selection: Any,
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
        auth_channel=auth_selection.channel,
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
    payload["auth_channel"] = auth_selection.to_dict()
    if approval_queue is not None and result.status == MCPResultStatus.APPROVAL_REQUIRED:
        queued = approval_queue.enqueue_mcp_result(payload)
        payload["approval_queue"] = {
            "path": str(approval_queue.path),
            "approval_id": queued.id,
            "status": queued.status.value,
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
        "--broker-cache-path",
        help="Explicit signed approval broker cache path.",
    )
    parser.add_argument(
        "--audit-path",
        help="Explicit local audit JSONL path.",
    )
    parser.add_argument(
        "--audit-sqlite-path",
        help="Explicit local SQLite audit path.",
    )
    parser.add_argument(
        "--auth-channel",
        choices=["mobile_signed", "local_terminal"],
        default=None,
        help=(
            "Override the operator auth channel. mobile_signed (ACT) is the "
            "recommended default; local_terminal is a less-secure opt-out."
        ),
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
    approval_actions.add_parser("watch")
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
    allow = approval_actions.add_parser("allow")
    allow.add_argument("approval_id")
    allow.add_argument("--operator-id", required=True)
    allow.add_argument("--session-id", required=True)
    allow.add_argument("--target", required=True)
    allow.add_argument("--provider", required=True)
    allow.add_argument("--capability", required=True)
    allow.add_argument("--params-fingerprint", required=True)
    allow.add_argument("--risk-family", required=True)
    allow.add_argument("--expires-at", required=True)
    allow.add_argument(
        "--channel",
        choices=[ApprovalChannel.OUT_OF_BAND.value, ApprovalChannel.WATCH_TUI.value],
        default=ApprovalChannel.WATCH_TUI.value,
    )
    allow.add_argument(
        "--dev-signer",
        action="store_true",
        help="Use the development/test signer. Not a production trust anchor.",
    )
    allow.add_argument(
        "--signer-key-id",
        default="agentickvm-dev-test-signer",
        help="Signer key id for the development/test signer.",
    )

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

    providers = subparsers.add_parser("providers")
    provider_actions = providers.add_subparsers(dest="providers_command")
    preflight = provider_actions.add_parser("preflight")
    preflight.add_argument("--target", required=True)
    preflight.add_argument("--external-config", required=True)
    preflight.add_argument("--artifact-path")
    preflight.add_argument("--credential-ref")
    preflight.add_argument("--live-provider-enabled", action="store_true")
    preflight.add_argument("--tls-reviewed", action="store_true")
    preflight.add_argument("--timeout-reviewed", action="store_true")
    preflight.add_argument("--manual-smoke-acknowledged", action="store_true")
    preflight.add_argument("--capability", action="append", default=[])
    preflight.add_argument("--ci-mode", action="store_true")
    preflight.add_argument("--test-mode", action="store_true")

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
    if args.approval_command in {"watch", "allow"}:
        return _broker_approvals(args)
    if args.approval_command == "deny" and approval_queue is None and args.broker_cache_path:
        _print_json(
            {
                "status": "approval_denied",
                "approval": {
                    "id": args.approval_id,
                    "operator_id": args.operator_id,
                    "reason": args.reason,
                    "operator_surface": "approval_broker_cli",
                    "grant_created": False,
                },
            }
        )
        return 0
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


def _broker_approvals(args: argparse.Namespace) -> int:
    if not args.broker_cache_path:
        raise ValueError("broker approval commands require --broker-cache-path")
    cache = SignedApprovalCache(args.broker_cache_path)
    if args.approval_command == "watch":
        try:
            grants = cache.read_signed_grants()
        except ApprovalCacheError as exc:
            _print_json(
                {
                    "status": "approval_cache_error",
                    "path": args.broker_cache_path,
                    "reason": str(exc),
                }
            )
            return 2
        _print_json(
            {
                "status": "ok",
                "operator_surface": "approval_broker_cli",
                "path": args.broker_cache_path,
                "authority": "cache_only_signature_required",
                "signed_grants": [
                    {
                        "grant_id": grant.payload.grant_id,
                        "request_id": grant.payload.request_id,
                        "session_id": grant.payload.session_id,
                        "target": grant.payload.target,
                        "provider": grant.payload.provider,
                        "capability": grant.payload.capability,
                        "risk_family": grant.payload.risk_family,
                        "channel": grant.payload.channel.value,
                        "expires_at": grant.payload.expires_at.astimezone(UTC).isoformat(),
                        "signer_key_id": grant.payload.signer_key_id,
                    }
                    for grant in grants
                ],
            }
        )
        return 0
    if args.approval_command == "allow":
        if not args.dev_signer:
            _print_json(
                {
                    "status": "validation_error",
                    "reason": (
                        "operator allow requires a configured signer; only "
                        "--dev-signer is available in this development build"
                    ),
                }
            )
            return 2
        payload = GrantPayload(
            grant_id=f"grant-{args.approval_id}",
            request_id=args.approval_id,
            session_id=args.session_id,
            target=args.target,
            provider=args.provider,
            capability=args.capability,
            params_fingerprint=args.params_fingerprint,
            risk_family=args.risk_family,
            channel=ApprovalChannel(args.channel),
            expires_at=_parse_utc_datetime(args.expires_at),
            one_time=True,
            signer_key_id=args.signer_key_id,
        )
        signer = HMACDevelopmentSigner(
            key_id=args.signer_key_id,
            secret=b"agentickvm-development-signer-not-production",
        )
        signed_grant = signer.sign(payload)
        cache.append_signed_grant(signed_grant)
        _print_json(
            {
                "status": "approval_granted",
                "operator_surface": "approval_broker_cli",
                "operator_id": args.operator_id,
                "path": args.broker_cache_path,
                "production_authority": False,
                "grant": {
                    "grant_id": signed_grant.payload.grant_id,
                    "request_id": signed_grant.payload.request_id,
                    "session_id": signed_grant.payload.session_id,
                    "target": signed_grant.payload.target,
                    "provider": signed_grant.payload.provider,
                    "capability": signed_grant.payload.capability,
                    "params_fingerprint": signed_grant.payload.params_fingerprint,
                    "risk_family": signed_grant.payload.risk_family,
                    "channel": signed_grant.payload.channel.value,
                    "expires_at": signed_grant.payload.expires_at.astimezone(UTC).isoformat(),
                    "signer_key_id": signed_grant.payload.signer_key_id,
                    "signature_algorithm": signed_grant.signature_algorithm,
                },
            }
        )
        return 0
    raise ValueError("unknown broker approvals command")


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


def _providers(args: argparse.Namespace) -> int:
    if args.providers_command == "preflight":
        result = _provider_preflight(args)
        _print_json(result.to_dict())
        return 0 if result.ok else 2
    raise ValueError("unknown providers command")


def _provider_preflight(args: argparse.Namespace):
    config = load_config(args.config)
    target = next((item for item in config.targets if item.id == args.target), None)
    if target is None:
        request = LiveProviderPreflightRequest(
            provider_type="unknown",
            target_id=args.target,
            live_provider_enabled=args.live_provider_enabled,
            external_config_path=args.external_config,
            credential_ref=args.credential_ref,
            audit_backend_configured=bool(args.audit_path or args.audit_sqlite_path),
            approval_transport_configured=bool(args.approval_path),
            artifact_path=args.artifact_path,
            tls_policy_reviewed=args.tls_reviewed,
            timeout_policy_reviewed=args.timeout_reviewed,
            manual_smoke_acknowledged=args.manual_smoke_acknowledged,
            ci_mode=args.ci_mode or detected_ci_mode(),
            test_mode=args.test_mode or detected_test_mode(),
            capabilities=tuple(args.capability),
            repo_root=str(Path.cwd()),
        )
        return run_live_provider_preflight(request)

    provider = next((item for item in config.providers if item.id == target.provider), None)
    if provider is None:
        provider_type = "unknown"
        provider_id = target.provider
        credential_ref = args.credential_ref
        committed_enabled = False
        capabilities = tuple(args.capability)
    else:
        provider_type = provider.type
        provider_id = provider.id
        credential_ref = args.credential_ref or provider.credential_ref
        committed_enabled = provider.enabled and bool(provider.metadata.get("live_mode", False))
        metadata_capabilities = provider.metadata.get("capabilities", ())
        if isinstance(metadata_capabilities, (list, tuple)):
            capabilities = tuple(str(item) for item in metadata_capabilities)
        else:
            capabilities = ()
        capabilities = tuple(args.capability) or capabilities

    return run_live_provider_preflight(
        LiveProviderPreflightRequest(
            provider_type=provider_type,
            provider_id=provider_id,
            target_id=args.target,
            live_provider_enabled=args.live_provider_enabled,
            external_config_path=args.external_config,
            credential_ref=credential_ref,
            audit_backend_configured=bool(args.audit_path or args.audit_sqlite_path),
            approval_transport_configured=bool(args.approval_path),
            artifact_path=args.artifact_path,
            tls_policy_reviewed=args.tls_reviewed,
            timeout_policy_reviewed=args.timeout_reviewed,
            manual_smoke_acknowledged=args.manual_smoke_acknowledged,
            ci_mode=args.ci_mode or detected_ci_mode(),
            test_mode=args.test_mode or detected_test_mode(),
            committed_config_provider_enabled=committed_enabled,
            capabilities=capabilities,
            repo_root=str(Path.cwd()),
        )
    )


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
    auth_selection: Any,
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
        "auth_channel": auth_selection.to_dict(),
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


def _parse_utc_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(UTC)


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
