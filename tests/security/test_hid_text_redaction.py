from __future__ import annotations

from agentickvm.control_plane import (
    Actor,
    ActorType,
    AuditEventType,
    CapabilityRef,
    PolicyDecision,
    build_audit_event,
)
from agentickvm.providers import MockProvider, ProviderActionRequest
from agentickvm.redaction import (
    REDACTED_HID_TEXT,
    hid_capture_posture,
    redact_hid_text,
    redact_mapping,
)


SYNTHETIC_PASSWORD = "password=correct-horse-battery-staple"
SYNTHETIC_TOKEN = "AbCdEfGhIjKlMnOpQrSt1234567890"
SYNTHETIC_MFA = "mfa=123456"


def _input_request(text: str) -> ProviderActionRequest:
    return ProviderActionRequest(
        capability="input.keyboard_type",
        action="keyboard_type",
        target_id="mock-host",
        session_id="hid-redaction-session",
        correlation_id="hid-redaction",
        parameters={"text": text},
    )


def test_typed_text_redacted_by_default_in_provider_result_shape() -> None:
    provider = MockProvider()

    result = provider.execute_authorized(_input_request(f"type {SYNTHETIC_PASSWORD}"))
    normalized = result.normalized()

    assert normalized["data"]["parameters"]["text"] == REDACTED_HID_TEXT
    assert SYNTHETIC_PASSWORD not in repr(normalized)
    assert normalized["data"]["input_events"][0]["parameters"]["text"] == REDACTED_HID_TEXT


def test_typed_text_redacted_by_default_in_audit() -> None:
    event = build_audit_event(
        event_type=AuditEventType.REQUEST_RECEIVED,
        correlation_id="hid-redaction",
        session_id="hid-redaction-session",
        actor=Actor(type=ActorType.AGENT, id="agent"),
        capability=CapabilityRef(id="input.keyboard_type", family="input", action="keyboard_type"),
        policy_decision=PolicyDecision.ASK_EACH_TIME,
        request={"text": f"type {SYNTHETIC_PASSWORD}"},
    )

    payload = event.to_dict()

    assert payload["request"]["text"] == REDACTED_HID_TEXT
    assert SYNTHETIC_PASSWORD not in repr(payload)
    assert "request.text" in payload["redactions"]


def test_full_capture_surfaces_more_text_but_strips_credentials() -> None:
    text = f"open BIOS user admin {SYNTHETIC_PASSWORD} {SYNTHETIC_MFA}"

    result = redact_hid_text(text, full_capture=True)

    assert "open BIOS user admin" in result.value
    assert "correct-horse-battery-staple" not in result.value
    assert "123456" not in result.value
    assert "[REDACTED]" in result.value


def test_high_entropy_token_backstop_redacts_outside_known_fields() -> None:
    payload, redactions = redact_mapping({"note": f"operator pasted {SYNTHETIC_TOKEN}"})

    assert payload["note"] == "[REDACTED]"
    assert "note" in redactions
    assert SYNTHETIC_TOKEN not in repr(payload)


def test_full_capture_posture_is_audited_as_reduced_protection() -> None:
    event = build_audit_event(
        event_type=AuditEventType.PROVIDER_EXECUTION_COMPLETED,
        correlation_id="hid-redaction",
        session_id="hid-redaction-session",
        actor=Actor(type=ActorType.AGENT, id="agent"),
        capability=CapabilityRef(id="input.keyboard_type", family="input", action="keyboard_type"),
        policy_decision=PolicyDecision.ASK_EACH_TIME,
        result={
            "hid_capture": hid_capture_posture(full_capture=True),
            "text": f"visible setup text {SYNTHETIC_PASSWORD}",
        },
    )

    payload = event.to_dict()

    assert payload["result"]["hid_capture"]["full_capture"] is True
    assert payload["result"]["hid_capture"]["posture"] == "full_capture_reduced_protection"
    assert "visible setup text" in payload["result"]["text"]
    assert "correct-horse-battery-staple" not in repr(payload)


def test_no_secret_shaped_string_survives_default_result_shape() -> None:
    provider = MockProvider()
    result = provider.execute_authorized(
        _input_request(f"{SYNTHETIC_PASSWORD} {SYNTHETIC_TOKEN} {SYNTHETIC_MFA}")
    )

    normalized = result.normalized()

    assert SYNTHETIC_PASSWORD not in repr(normalized)
    assert SYNTHETIC_TOKEN not in repr(normalized)
    assert SYNTHETIC_MFA not in repr(normalized)
