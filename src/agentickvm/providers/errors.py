"""Provider error taxonomy.

Provider errors normalize into provider action results so interface layers can
return structured failures without exposing secrets or provider internals.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentickvm.providers.base import ProviderActionRequest, ProviderActionResult


@dataclass(frozen=True)
class ProviderErrorInfo:
    """Static provider error metadata."""

    code: str
    category: str
    retryable: bool
    safe_to_show: bool
    audit_severity: str
    stop_behavior: str
    approval_could_resolve: bool


class ProviderError(RuntimeError):
    """Base provider error with structured normalization."""

    info = ProviderErrorInfo(
        code="provider_error",
        category="provider",
        retryable=False,
        safe_to_show=True,
        audit_severity="medium",
        stop_behavior="stop_action",
        approval_could_resolve=False,
    )
    default_message = "provider error"

    def __init__(self, message: str | None = None, *, detail: str | None = None) -> None:
        self.message = message or self.default_message
        self.detail = detail
        super().__init__(self.message)

    @property
    def public_message(self) -> str:
        """Return safe text for CLI, MCP, docs, and audit summaries."""

        if self.info.safe_to_show:
            return _redact_text(self.message)
        return self.default_message

    def to_provider_result(
        self,
        *,
        request: ProviderActionRequest,
        provider_id: str,
        provider_type: str,
    ) -> ProviderActionResult:
        """Normalize the error into a structured provider result."""

        return ProviderActionResult(
            ok=False,
            provider_id=provider_id,
            provider_type=provider_type,
            capability=request.capability,
            action=request.action,
            target_id=request.target_id,
            performed_on_hardware=False,
            message=self.public_message,
            data={
                "error": {
                    "code": self.info.code,
                    "category": self.info.category,
                    "audit_severity": self.info.audit_severity,
                    "stop_behavior": self.info.stop_behavior,
                    "approval_could_resolve": self.info.approval_could_resolve,
                }
            },
            error_code=self.info.code,
            error_message=self.public_message,
            retryable=self.info.retryable,
            warnings=(_redact_text(self.detail),) if self.detail and self.info.safe_to_show else (),
        )


class ProviderDisabledError(ProviderError):
    info = ProviderErrorInfo("provider_disabled", "config", False, True, "medium", "stop_action", False)
    default_message = "provider is disabled"


class ProviderNotFoundError(ProviderError):
    info = ProviderErrorInfo("provider_not_found", "config", False, True, "medium", "stop_action", False)
    default_message = "provider not found"


class TargetNotFoundError(ProviderError):
    info = ProviderErrorInfo("target_not_found", "config", False, True, "medium", "stop_action", False)
    default_message = "target not found"


class UnsupportedCapabilityError(ProviderError):
    info = ProviderErrorInfo("unsupported_capability", "provider", False, True, "medium", "stop_action", False)
    default_message = "unsupported capability"


class ProviderTimeoutError(ProviderError):
    info = ProviderErrorInfo("provider_timeout", "network", True, True, "medium", "retry_allowed", False)
    default_message = "provider timeout"


class ProviderTLSVerificationError(ProviderError):
    info = ProviderErrorInfo("provider_tls_verification", "network", False, True, "high", "stop_action", False)
    default_message = "provider TLS verification failed"


class ProviderAuthenticationRequiredError(ProviderError):
    info = ProviderErrorInfo(
        "provider_authentication_required",
        "credential",
        False,
        False,
        "high",
        "stop_action",
        True,
    )
    default_message = "provider authentication required"


class ProviderAuthenticationFailedError(ProviderError):
    info = ProviderErrorInfo(
        "provider_authentication_failed",
        "credential",
        False,
        False,
        "high",
        "stop_action",
        True,
    )
    default_message = "provider authentication failed"


class ProviderAuthorizationError(ProviderError):
    info = ProviderErrorInfo("provider_authorization", "credential", False, False, "high", "stop_action", True)
    default_message = "provider authorization failed"


class ProviderConnectionError(ProviderError):
    info = ProviderErrorInfo("provider_connection", "network", True, True, "medium", "retry_allowed", False)
    default_message = "provider connection failed"


class ProviderProtocolError(ProviderError):
    info = ProviderErrorInfo("provider_protocol", "protocol", False, True, "medium", "stop_action", False)
    default_message = "provider protocol error"


class ProviderResponseValidationError(ProviderError):
    info = ProviderErrorInfo("provider_response_validation", "protocol", False, True, "medium", "stop_action", False)
    default_message = "provider response validation failed"


class ProviderRateLimitedError(ProviderError):
    info = ProviderErrorInfo("provider_rate_limited", "provider", True, True, "medium", "retry_allowed", False)
    default_message = "provider rate limited"


class ProviderUnsafeOperationError(ProviderError):
    info = ProviderErrorInfo("provider_unsafe_operation", "safety", False, True, "critical", "stop_session", False)
    default_message = "provider unsafe operation blocked"


class ProviderMutationBlockedError(ProviderError):
    info = ProviderErrorInfo("provider_mutation_blocked", "safety", False, True, "critical", "stop_action", False)
    default_message = "provider mutation blocked"


class ProviderSecretRequiredError(ProviderError):
    info = ProviderErrorInfo("provider_secret_required", "credential", False, False, "high", "stop_action", True)
    default_message = "provider secret reference required"


class ProviderConfigError(ProviderError):
    info = ProviderErrorInfo("provider_config", "config", False, True, "medium", "stop_action", False)
    default_message = "provider config error"


PROVIDER_ERROR_TYPES = (
    ProviderDisabledError,
    ProviderNotFoundError,
    TargetNotFoundError,
    UnsupportedCapabilityError,
    ProviderTimeoutError,
    ProviderTLSVerificationError,
    ProviderAuthenticationRequiredError,
    ProviderAuthenticationFailedError,
    ProviderAuthorizationError,
    ProviderConnectionError,
    ProviderProtocolError,
    ProviderResponseValidationError,
    ProviderRateLimitedError,
    ProviderUnsafeOperationError,
    ProviderMutationBlockedError,
    ProviderSecretRequiredError,
    ProviderConfigError,
)


def _redact_text(value: str) -> str:
    lowered = value.lower()
    if any(fragment in lowered for fragment in ("password", "token", "secret", "credential")):
        return "[REDACTED]"
    return value


__all__ = [
    "PROVIDER_ERROR_TYPES",
    "ProviderAuthenticationFailedError",
    "ProviderAuthenticationRequiredError",
    "ProviderAuthorizationError",
    "ProviderConfigError",
    "ProviderConnectionError",
    "ProviderDisabledError",
    "ProviderError",
    "ProviderErrorInfo",
    "ProviderMutationBlockedError",
    "ProviderNotFoundError",
    "ProviderProtocolError",
    "ProviderRateLimitedError",
    "ProviderResponseValidationError",
    "ProviderSecretRequiredError",
    "ProviderTLSVerificationError",
    "ProviderTimeoutError",
    "ProviderUnsafeOperationError",
    "TargetNotFoundError",
    "UnsupportedCapabilityError",
]
