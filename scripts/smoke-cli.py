#!/usr/bin/env python3
"""Run a mock-only AgenticKVM CLI smoke matrix."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentickvm.cli import main as cli_main  # noqa: E402


FORBIDDEN_OUTPUT = (
    "mcp==1.27.2",
    "password",
    "api_key",
    "private_key",
    "bearer ",
    "session_cookie",
)


@dataclass(frozen=True)
class SmokeCase:
    name: str
    argv: tuple[str, ...]
    expected_exit: int
    expected_status: str | None = None
    expected_key: str | None = None


CASES: tuple[SmokeCase, ...] = (
    SmokeCase("list-providers", ("list-providers",), 0, expected_key="providers"),
    SmokeCase("list-targets", ("list-targets",), 0, expected_key="targets"),
    SmokeCase(
        "mock-observe-screen",
        ("call", "--target", "mock-host", "--tool", "observe_screen"),
        0,
        "ok",
    ),
    SmokeCase(
        "mock-power-state",
        ("call", "--target", "mock-host", "--tool", "get_power_state"),
        0,
        "ok",
    ),
    SmokeCase(
        "pikvm-fixture-observe-screen",
        (
            "--config",
            "examples/config/pikvm-observe-fixture.yaml",
            "call",
            "--target",
            "pikvm-fixture-target",
            "--provider",
            "pikvm-fixture",
            "--tool",
            "observe_screen",
        ),
        0,
        "ok",
    ),
    SmokeCase(
        "unknown-tool",
        ("call", "--target", "mock-host", "--tool", "provider_raw_reset"),
        2,
        "validation_error",
    ),
    SmokeCase(
        "unknown-target",
        ("call", "--target", "missing", "--tool", "get_power_state"),
        2,
        "validation_error",
    ),
    SmokeCase(
        "disabled-provider-target",
        (
            "--config",
            "examples/config/provider-placeholders.yaml",
            "call",
            "--target",
            "disabled-pikvm-target",
            "--provider",
            "pikvm-placeholder",
            "--tool",
            "get_power_state",
        ),
        2,
        "validation_error",
    ),
    SmokeCase(
        "dangerous-action-gated",
        ("call", "--target", "mock-host", "--tool", "force_restart"),
        0,
        "approval_required",
    ),
    SmokeCase(
        "raw-secret-reveal-denied",
        ("call", "--target", "mock-host", "--tool", "reveal_secret"),
        0,
        "denied",
    ),
    SmokeCase(
        "policy-modification-denied",
        ("call", "--target", "mock-host", "--tool", "modify_policy"),
        0,
        "denied",
    ),
)


class SmokeFailure(RuntimeError):
    """Raised when a CLI smoke case fails."""


def main() -> int:
    results: list[dict[str, Any]] = []
    try:
        for case in CASES:
            results.append(_run_case(case))
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc), "cases": results}))
        return 1
    print(json.dumps({"status": "ok", "cases": results}, sort_keys=True))
    return 0


def _run_case(case: SmokeCase) -> dict[str, Any]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = cli_main(list(case.argv))
    raw = buffer.getvalue().strip()
    if exit_code != case.expected_exit:
        raise SmokeFailure(
            f"{case.name} exit {exit_code}, expected {case.expected_exit}: {raw}"
        )
    payload = json.loads(raw)
    _assert_json_safe(payload)
    _assert_output_redacted(raw)
    if case.expected_key is not None and case.expected_key not in payload:
        raise SmokeFailure(f"{case.name} missing key {case.expected_key}")
    if case.expected_status is not None and payload.get("status") != case.expected_status:
        raise SmokeFailure(
            f"{case.name} status {payload.get('status')}, expected {case.expected_status}"
        )
    return {
        "name": case.name,
        "exit_code": exit_code,
        "status": payload.get("status", "ok"),
        "provider": payload.get("provider"),
        "target": payload.get("target"),
    }


def _assert_json_safe(payload: Any) -> None:
    json.loads(json.dumps(payload, sort_keys=True))


def _assert_output_redacted(raw: str) -> None:
    lowered = raw.lower()
    for forbidden in FORBIDDEN_OUTPUT:
        if forbidden in lowered:
            raise SmokeFailure(f"CLI smoke output contains forbidden text: {forbidden}")


if __name__ == "__main__":
    raise SystemExit(main())
