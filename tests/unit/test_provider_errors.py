from agentickvm.providers import (
    PROVIDER_ERROR_TYPES,
    ProviderActionRequest,
    ProviderAuthenticationFailedError,
    ProviderMutationBlockedError,
    ProviderUnsafeOperationError,
    UnsupportedCapabilityError,
)


def _request() -> ProviderActionRequest:
    return ProviderActionRequest(
        capability="observe.power_state",
        action="power_state",
        target_id="error-target",
        session_id="s1",
        correlation_id="corr-error",
    )


def test_all_provider_errors_normalize_into_structured_results() -> None:
    for error_type in PROVIDER_ERROR_TYPES:
        error = error_type()
        result = error.to_provider_result(
            request=_request(),
            provider_id="redfish-fixture",
            provider_type="redfish",
        )
        normalized = result.normalized()

        assert normalized["status"] == "error"
        assert normalized["provider_id"] == "redfish-fixture"
        assert normalized["provider_type"] == "redfish"
        assert normalized["error_code"] == error.info.code
        assert normalized["retryable"] is error.info.retryable
        assert normalized["performed_on_hardware"] is False
        assert normalized["data"]["error"]["category"] == error.info.category
        assert normalized["data"]["error"]["audit_severity"] == error.info.audit_severity


def test_sensitive_error_details_are_redacted() -> None:
    error = UnsupportedCapabilityError(
        "token should not be shown",
        detail="password should not be shown",
    )
    result = error.to_provider_result(
        request=_request(),
        provider_id="mock",
        provider_type="mock",
    )
    normalized = result.normalized()

    assert normalized["error_message"] == "[REDACTED]"
    assert normalized["warnings"] == ["[REDACTED]"]
    assert "token should not be shown" not in repr(normalized)
    assert "password should not be shown" not in repr(normalized)


def test_unsafe_operation_errors_are_not_retryable() -> None:
    for error in (ProviderUnsafeOperationError(), ProviderMutationBlockedError()):
        result = error.to_provider_result(
            request=_request(),
            provider_id="pikvm-fixture",
            provider_type="pikvm",
        )

        assert result.retryable is False
        assert result.normalized()["data"]["error"]["category"] == "safety"


def test_auth_errors_do_not_leak_credentials() -> None:
    error = ProviderAuthenticationFailedError("password=opensesame")
    result = error.to_provider_result(
        request=_request(),
        provider_id="redfish-fixture",
        provider_type="redfish",
    )
    normalized = result.normalized()

    assert normalized["error_message"] == "provider authentication failed"
    assert "opensesame" not in repr(normalized)
