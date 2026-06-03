import json

import pytest

from agentickvm.cli import main as cli_main
from agentickvm.config import build_runtime, mock_only_config
from agentickvm.control_plane import ControlMode, mode_preset
from agentickvm.mcp import MCPRouter, MCPToolRequest

MATRIX = {
    "Observe": {
        "observe_screen": "ok",
        "get_power_state": "ok",
        "power_on": "denied",
        "graceful_restart": "denied",
        "force_restart": "denied",
        "change_boot_order": "denied",
        "reveal_secret": "denied",
        "modify_policy": "denied",
    },
    "Assisted": {
        "observe_screen": "ok",
        "get_power_state": "ok",
        "power_on": "approval_required",
        "graceful_restart": "approval_required",
        "force_restart": "denied",
        "change_boot_order": "denied",
        "reveal_secret": "denied",
        "modify_policy": "denied",
    },
    "Supervised": {
        "observe_screen": "ok",
        "get_power_state": "ok",
        "power_on": "approval_required",
        "graceful_restart": "approval_required",
        "force_restart": "approval_required",
        "change_boot_order": "approval_required",
        "reveal_secret": "denied",
        "modify_policy": "denied",
    },
    "Full Control": {
        "observe_screen": "ok",
        "get_power_state": "ok",
        "power_on": "ok",
        "graceful_restart": "ok",
        "force_restart": "ok",
        "change_boot_order": "ok",
        "reveal_secret": "denied",
        "modify_policy": "denied",
    },
}


def _mcp_status(mode: str, tool: str) -> str:
    runtime = build_runtime(mock_only_config())
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=mode_preset(mode),
        audit_sink=runtime.audit_sink,
    )
    result = router.handle_tool_request(
        MCPToolRequest(
            tool_name=tool,
            target="mock-host",
            session_id="s1",
            requester_id="agent-1",
        )
    )
    return result.status.value


def _cli_status(mode: str, tool: str, capsys) -> str:
    exit_code = cli_main(
        [
            "call",
            "--target",
            "mock-host",
            "--tool",
            tool,
            "--mode",
            mode,
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    return payload["status"]


@pytest.mark.parametrize("mode", MATRIX)
@pytest.mark.parametrize(
    "tool",
    [
        "observe_screen",
        "get_power_state",
        "power_on",
        "graceful_restart",
        "force_restart",
        "change_boot_order",
        "reveal_secret",
        "modify_policy",
    ],
)
def test_cli_and_mcp_status_matrix_agree(mode: str, tool: str, capsys) -> None:
    expected = MATRIX[mode][tool]

    assert _mcp_status(mode, tool) == expected
    assert _cli_status(mode, tool, capsys) == expected


def test_matrix_covers_visible_modes() -> None:
    assert set(MATRIX) == {
        ControlMode.OBSERVE.value,
        ControlMode.ASSISTED.value,
        ControlMode.SUPERVISED.value,
        ControlMode.FULL_CONTROL.value,
    }


def test_unknown_tool_consistency_fails_closed(capsys) -> None:
    runtime = build_runtime(mock_only_config())
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=mode_preset(ControlMode.FULL_CONTROL),
        audit_sink=runtime.audit_sink,
    )
    mcp_result = router.handle_tool_request(
        MCPToolRequest(
            tool_name="provider_raw_reset",
            target="mock-host",
            session_id="s1",
            requester_id="agent-1",
        )
    )
    cli_exit = cli_main(
        [
            "call",
            "--target",
            "mock-host",
            "--tool",
            "provider_raw_reset",
            "--mode",
            "Full Control",
        ]
    )
    cli_payload = json.loads(capsys.readouterr().out)

    assert mcp_result.status.value == "validation_error"
    assert cli_exit == 2
    assert cli_payload["status"] == "validation_error"
