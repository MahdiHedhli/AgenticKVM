from agentickvm import __version__
from agentickvm.control_plane import CONTROL_MODES, UNKNOWN_CAPABILITY_DECISION
from agentickvm.providers import MockProvider


def test_package_imports() -> None:
    assert __version__ == "0.0.0"
    assert "Observe" in CONTROL_MODES
    assert UNKNOWN_CAPABILITY_DECISION == "deny"
    assert MockProvider.provider_id == "mock"
