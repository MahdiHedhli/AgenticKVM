#!/usr/bin/env python3
"""Operator-run PiKVM live validation harness.

This script is intentionally one-stage-at-a-time. It never chains stages and it
does not run in CI. Stages touching real hardware require an operator-written
preconditions JSON file and explicit command invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentickvm.live_validation.pikvm import (  # noqa: E402
    PiKVMLiveValidationError,
    RealTLSPiKVMProbe,
    build_stage_checkpoint,
    load_preconditions,
    run_stage1_cert_preflight,
    validate_prior_checkpoint,
)


PRECONDITIONS_TEMPLATE = {
    "sacrificial_target": "REQUIRED: reimageable host identity",
    "isolated_segment": "REQUIRED: isolated VLAN/network segment",
    "credential_ref": "env:AGENTICKVM_PIKVM_VALIDATION_CREDENTIAL or keychain://...",
    "firmware_version": "REQUIRED: trusted PiKVM firmware version",
    "operator": "REQUIRED: human operator name",
    "confirmed_at": "REQUIRED: ISO-8601 timestamp",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "preconditions-template":
            _write_json(Path(args.output), PRECONDITIONS_TEMPLATE)
            return 0
        if args.command == "stage1-preflight":
            _require_preconditions(args.preconditions)
            checkpoint = run_stage1_cert_preflight(
                base_url=args.base_url,
                credential_ref=args.credential_ref,
                cert_fingerprint=args.cert_fingerprint,
                verify_ssl=args.verify_ssl,
                tls_probe=RealTLSPiKVMProbe(),
            )
            _write_json(Path(args.output), checkpoint.to_dict())
            return 0
        if args.command == "stage2-observe":
            return _manual_checkpoint(
                args,
                prior_stage="stage1-cert-pinning-preflight",
                stage="stage2-observe",
                next_stage="stage3-lowest-risk-actuation",
                details={
                    "manual_actions": [
                        "Capture real screenshot or MJPEG snapshot.",
                        "Read real ATX power state.",
                        "Read real device information.",
                        "Confirm real screen text is redacted in result and audit output.",
                    ],
                    "automated_live_execution": False,
                    "reason": "live authenticated PiKVM HTTP client is not implemented yet",
                },
            )
        if args.command == "stage3-lowest-risk-actuation":
            return _manual_checkpoint(
                args,
                prior_stage="stage2-observe",
                stage="stage3-lowest-risk-actuation",
                next_stage="stage4-power-actuation",
                details={
                    "manual_actions": [
                        "Run one lowest-risk HID action with operator present.",
                        "Confirm clearance_required blocks without mock-cleared operator advance.",
                        "Confirm the mock-cleared path executes once.",
                        "Confirm HID text is redacted in the real audit record.",
                    ],
                    "automated_live_execution": False,
                    "reason": "real ACT transport is not published and hardware actuation is manual only",
                },
            )
        if args.command == "stage4-power-actuation":
            return _manual_checkpoint(
                args,
                prior_stage="stage3-lowest-risk-actuation",
                stage="stage4-power-actuation",
                next_stage=None,
                details={
                    "manual_actions": [
                        "Run one least-destructive power action with operator present.",
                        "Confirm the sacrificial target physically responds as expected.",
                        "Confirm target/action binding rejects a different target or action.",
                    ],
                    "automated_live_execution": False,
                    "reason": "power actuation against real hardware is manual checkpoint only",
                },
            )
        if args.command == "calibration":
            return _manual_checkpoint(
                args,
                prior_stage="stage2-observe",
                stage="mouse-calibration",
                next_stage="stage3-lowest-risk-actuation",
                details={
                    "manual_actions": [
                        "Use the screenshot coordinate map against the real display.",
                        "Verify a known visual point maps to the expected absolute HID coordinate.",
                        "Do not click until operator explicitly advances to Stage 3.",
                    ],
                    "automated_live_execution": False,
                },
            )
    except Exception as exc:  # noqa: BLE001 - operator script must fail clearly.
        print(json.dumps({"status": "error", "reason": str(exc)}, sort_keys=True))
        return 2
    parser.print_help(sys.stderr)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pikvm-live-validation.py")
    subparsers = parser.add_subparsers(dest="command")

    template = subparsers.add_parser("preconditions-template")
    template.add_argument("--output", required=True)

    stage1 = subparsers.add_parser("stage1-preflight")
    _add_common_live_args(stage1)
    stage1.add_argument("--base-url", required=True)
    stage1.add_argument("--credential-ref", required=True)
    stage1.add_argument("--cert-fingerprint")
    stage1.add_argument("--verify-ssl", action=argparse.BooleanOptionalAction, default=True)

    for command in (
        "stage2-observe",
        "stage3-lowest-risk-actuation",
        "stage4-power-actuation",
        "calibration",
    ):
        stage = subparsers.add_parser(command)
        _add_common_live_args(stage)
        stage.add_argument("--previous-checkpoint", required=True)
    return parser


def _add_common_live_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preconditions", required=True)
    parser.add_argument("--output", required=True)


def _require_preconditions(path: str) -> None:
    load_preconditions(path)


def _manual_checkpoint(
    args: argparse.Namespace,
    *,
    prior_stage: str,
    stage: str,
    next_stage: str | None,
    details: dict[str, Any],
) -> int:
    _require_preconditions(args.preconditions)
    validate_prior_checkpoint(args.previous_checkpoint, expected_stage=prior_stage)
    checkpoint = build_stage_checkpoint(
        stage=stage,
        status="operator_manual_execution_required",
        next_stage=next_stage,
        details=details,
    )
    _write_json(Path(args.output), checkpoint.to_dict())
    return 0


def _write_json(path: Path, payload: Any) -> None:
    if path.exists() and path.is_dir():
        raise PiKVMLiveValidationError("output path must be a file")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(path)}, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
