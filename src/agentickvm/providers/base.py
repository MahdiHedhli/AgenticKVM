"""Base provider contract.

Provider adapters execute already-authorized capability requests. They do not
own policy and must not be called directly by tools, CLI commands, API handlers,
or agent workflows.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class ProviderActionRequest:
    """A provider request after control-plane authorization."""

    capability: str
    action: str
    target_id: str
    session_id: str
    correlation_id: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def redacted_parameters(self) -> Mapping[str, Any]:
        """Return parameters with obvious secret-shaped keys redacted."""

        redacted: dict[str, Any] = {}
        for key, value in self.parameters.items():
            lowered = key.lower()
            if "secret" in lowered or "password" in lowered or "token" in lowered:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value
        return MappingProxyType(redacted)


@dataclass(frozen=True)
class ProviderActionResult:
    """Structured provider result."""

    ok: bool
    provider_id: str
    capability: str
    action: str
    target_id: str
    performed_on_hardware: bool
    message: str
    data: Mapping[str, Any] = field(default_factory=dict)
    provider_type: str | None = None
    warnings: tuple[str, ...] = ()
    redacted: bool = True
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    timestamp: str | None = None

    def normalized(self) -> dict[str, Any]:
        """Return a provider-neutral, secret-redacted result envelope."""

        payload: dict[str, Any] = {
            "status": "ok" if self.ok else "error",
            "provider_id": self.provider_id,
            "provider_type": self.provider_type or self.provider_id,
            "target": self.target_id,
            "capability": self.capability,
            "data": _redact_value(dict(self.data)),
            "warnings": list(self.warnings),
            "redacted": self.redacted,
            "error_code": self.error_code,
            "error_message": _redact_value(self.error_message or ""),
            "retryable": self.retryable,
            "performed_on_hardware": self.performed_on_hardware,
        }
        if self.timestamp is not None:
            payload["timestamp"] = self.timestamp
        return payload


@dataclass(frozen=True)
class ProviderStatus:
    """Safe provider status summary."""

    provider_id: str
    provider_kind: str
    enabled: bool
    is_real_hardware: bool
    risk_class: str
    supported_capabilities: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ProviderValidationResult:
    """Dry-run validation result before provider execution."""

    ok: bool
    provider_id: str
    capability: str
    message: str


class Provider(ABC):
    """Abstract provider adapter."""

    provider_id: str
    provider_kind: str
    enabled: bool = True
    is_real_hardware: bool
    risk_class: str = "unknown"
    supported_capabilities: frozenset[str]

    def supports(self, capability: str) -> bool:
        """Return whether the adapter has a mapping for a capability."""

        return capability in self.supported_capabilities

    def status(self) -> ProviderStatus:
        """Return a safe provider status summary without network calls."""

        return ProviderStatus(
            provider_id=self.provider_id,
            provider_kind=self.provider_kind,
            enabled=self.enabled,
            is_real_hardware=self.is_real_hardware,
            risk_class=self.risk_class,
            supported_capabilities=tuple(sorted(self.supported_capabilities)),
            message="provider status is local only",
        )

    def validate_authorized(
        self,
        request: ProviderActionRequest,
    ) -> ProviderValidationResult:
        """Validate an authorized provider request without executing it."""

        if not self.enabled:
            return ProviderValidationResult(
                ok=False,
                provider_id=self.provider_id,
                capability=request.capability,
                message="provider is disabled",
            )
        if not self.supports(request.capability):
            return ProviderValidationResult(
                ok=False,
                provider_id=self.provider_id,
                capability=request.capability,
                message="unsupported capability",
            )
        return ProviderValidationResult(
            ok=True,
            provider_id=self.provider_id,
            capability=request.capability,
            message="provider request is locally valid",
        )

    @abstractmethod
    def execute_authorized(
        self,
        request: ProviderActionRequest,
    ) -> ProviderActionResult:
        """Execute an already-authorized request."""


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in ("secret", "password", "token")):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = _redact_value(child)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value
