from agentickvm.control_plane import redact_mapping


def test_redact_mapping_redacts_secret_shaped_fields_recursively() -> None:
    redacted, paths = redact_mapping(
        {
            "password": "secret",
            "normal": "visible",
            "children": [
                {"token": "hidden"},
                {"name": "safe"},
            ],
            "otp_secret": "123456",
        }
    )

    assert redacted["password"] == "[REDACTED]"
    assert redacted["normal"] == "visible"
    assert redacted["children"][0]["token"] == "[REDACTED]"
    assert redacted["children"][1]["name"] == "safe"
    assert redacted["otp_secret"] == "[REDACTED]"
    assert set(paths) == {
        "password",
        "children[0].token",
        "otp_secret",
    }


def test_redact_mapping_redacts_hid_text_by_default() -> None:
    redacted, paths = redact_mapping({"text": "operator typed value"})

    assert redacted["text"] == "[REDACTED]"
    assert paths == ("text",)
