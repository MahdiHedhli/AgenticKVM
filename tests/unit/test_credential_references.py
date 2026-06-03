import json

import pytest

from agentickvm.config import ConfigValidationError, build_runtime, load_config
from agentickvm.control_plane import redact_mapping


def test_credential_ref_is_parsed_but_not_resolved(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENTICKVM_LAB_PIKVM_CREDENTIAL", "must-not-be-read")
    path = tmp_path / "credential-ref.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "pikvm-placeholder",
                        "type": "pikvm",
                        "enabled": False,
                        "credential_ref": "env://AGENTICKVM_LAB_PIKVM_CREDENTIAL",
                    }
                ],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path)
    runtime = build_runtime(config)

    assert config.providers[0].credential_ref == "env://AGENTICKVM_LAB_PIKVM_CREDENTIAL"
    assert "must-not-be-read" not in repr(config)
    assert "credential_ref" not in repr(runtime.provider_registry.list_summaries())


def test_raw_secret_fields_are_still_rejected(tmp_path) -> None:
    path = tmp_path / "raw-secret.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "pikvm-placeholder",
                        "type": "pikvm",
                        "enabled": False,
                        "password": "do-not-store",
                    }
                ],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError, match="Secret-like config key"):
        load_config(path)


def test_invalid_credential_ref_scheme_rejected(tmp_path) -> None:
    path = tmp_path / "bad-ref.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "pikvm-placeholder",
                        "type": "pikvm",
                        "enabled": False,
                        "credential_ref": "raw-password-value",
                    }
                ],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError, match="Unsupported credential reference"):
        load_config(path)


def test_credential_ref_is_redacted_for_audit_payloads() -> None:
    redacted, paths = redact_mapping(
        {"credential_ref": "env://AGENTICKVM_LAB_PIKVM_CREDENTIAL"}
    )

    assert redacted["credential_ref"] == "[REDACTED]"
    assert paths == ("credential_ref",)
