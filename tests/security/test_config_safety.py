import json

import pytest

from agentickvm.config import ConfigValidationError, load_config


def test_secret_like_config_keys_are_rejected(tmp_path) -> None:
    path = tmp_path / "secret.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "mock",
                        "type": "mock",
                        "metadata": {"password": "must-not-load"},
                    }
                ],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError, match="Secret-like config key"):
        load_config(path)


def test_dynamic_import_config_keys_are_rejected(tmp_path) -> None:
    path = tmp_path / "dynamic.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "mock",
                        "type": "mock",
                        "module": "agentickvm.providers.mock",
                    }
                ],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError, match="Dynamic import config key"):
        load_config(path)


def test_config_loader_does_not_require_environment_secrets(monkeypatch) -> None:
    monkeypatch.delenv("AGENTICKVM_TOKEN", raising=False)
    monkeypatch.delenv("AGENTICKVM_PASSWORD", raising=False)

    config = load_config()

    assert config.providers[0].id == "mock"
    assert config.targets[0].id == "mock-host"
