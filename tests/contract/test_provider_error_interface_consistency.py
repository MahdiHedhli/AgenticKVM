import json

from agentickvm.cli import main as cli_main
from agentickvm.config import build_runtime, config_from_mapping
from agentickvm.control_plane import ControlMode, mode_preset
from agentickvm.mcp import MCPRouter, MCPToolRequest


def _fake_config() -> dict:
    return {
        "version": "0.1",
        "providers": [
            {
                "id": "redfish-fixture",
                "type": "redfish",
                "enabled": True,
                "metadata": {"fixture_mode": True},
            }
        ],
        "targets": [
            {
                "id": "redfish-target",
                "provider": "redfish-fixture",
                "enabled": True,
                "allowed_modes": ["Full Control"],
            }
        ],
        "default_policy": {"mode": "Full Control"},
    }


def test_mcp_translates_provider_errors_consistently() -> None:
    runtime = build_runtime(config_from_mapping(_fake_config()))
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=mode_preset(ControlMode.FULL_CONTROL),
        audit_sink=runtime.audit_sink,
    )

    result = router.handle_tool_request(
        MCPToolRequest(
            tool_name="type_text",
            target="redfish-target",
            session_id="s1",
            requester_id="agent-1",
        )
    )
    provider_result = result.to_dict()["data"]["provider_result"]

    assert result.status.value == "provider_error"
    assert provider_result["status"] == "error"
    assert provider_result["provider_type"] == "redfish"
    assert provider_result["error_code"] == "unsupported_capability"
    assert provider_result["retryable"] is False


def test_cli_translates_provider_errors_consistently(tmp_path, capsys) -> None:
    path = tmp_path / "redfish-fixture.yaml"
    path.write_text(json.dumps(_fake_config()), encoding="utf-8")

    exit_code = cli_main(
        [
            "--config",
            str(path),
            "call",
            "--target",
            "redfish-target",
            "--tool",
            "type_text",
            "--mode",
            "Full Control",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    provider_result = payload["data"]["provider_result"]

    assert exit_code == 2
    assert payload["status"] == "provider_error"
    assert provider_result["status"] == "error"
    assert provider_result["provider_type"] == "redfish"
    assert provider_result["error_code"] == "unsupported_capability"
    assert provider_result["retryable"] is False
