"""CLI happy-path smoke routine, including the selectable auth-channel surface.

Drives the real CLI entrypoint (mock-only config) and asserts the operator-facing
output is structured, safe, and surfaces the selected auth channel and its
opt-out warning. No network, no hardware.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentickvm.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[2]
PIKVM_FIXTURE_CONFIG = ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml"


def _run_cli(argv, capsys):
    exit_code = cli_main(argv)
    out = capsys.readouterr().out
    return exit_code, json.loads(out)


def test_status_reports_default_mobile_signed_channel(capsys) -> None:
    code, payload = _run_cli(["status"], capsys)

    assert code == 0
    channel = payload["auth_channel"]
    assert channel["channel"] == "mobile_signed"
    assert channel["recommended"] is True
    assert channel["is_default"] is True
    assert channel["warning"] is None
    assert payload["safety"]["live_providers_enabled_by_default"] is False


def test_status_local_terminal_opt_out_surfaces_warning(capsys) -> None:
    code, payload = _run_cli(["--auth-channel", "local_terminal", "status"], capsys)

    assert code == 0
    channel = payload["auth_channel"]
    assert channel["channel"] == "local_terminal"
    assert channel["recommended"] is False
    assert "less secure" in channel["warning"]


def test_list_providers_and_targets_are_safe(capsys) -> None:
    providers_code, providers = _run_cli(
        ["--config", str(PIKVM_FIXTURE_CONFIG), "list-providers"], capsys
    )
    targets_code, targets = _run_cli(
        ["--config", str(PIKVM_FIXTURE_CONFIG), "list-targets"], capsys
    )

    assert providers_code == 0
    assert providers["providers"][0]["id"] == "pikvm-fixture"
    assert targets_code == 0
    assert targets["targets"][0]["id"] == "pikvm-fixture-target"
    assert "credential_ref" not in repr(providers)
    assert "keychain://" not in repr(providers)


def test_cli_observe_call_happy_path_is_redacted(capsys) -> None:
    code, payload = _run_cli(
        [
            "--config",
            str(PIKVM_FIXTURE_CONFIG),
            "call",
            "--target",
            "pikvm-fixture-target",
            "--tool",
            "observe_screen",
        ],
        capsys,
    )

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["data"]["provider_result"]["data"]["screen"]["content"] == "[REDACTED]"
    assert payload["auth_channel"]["channel"] == "mobile_signed"


def test_cli_actuation_call_fails_closed_in_observe_config(capsys) -> None:
    code, payload = _run_cli(
        [
            "--config",
            str(PIKVM_FIXTURE_CONFIG),
            "call",
            "--target",
            "pikvm-fixture-target",
            "--tool",
            "power_on",
        ],
        capsys,
    )

    assert code == 0
    assert payload["status"] == "denied"
    assert payload["capability"] == "power.on"
