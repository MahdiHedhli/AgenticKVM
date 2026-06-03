"""Transport security policy for future live observe providers.

This model does not implement live transport. It captures defaults and
validation rules that future transports must satisfy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

RETRYABLE_ERROR_CODES = frozenset(
    {
        "provider_timeout",
        "provider_connection",
        "provider_rate_limited",
    }
)
UNSAFE_CAPABILITY_PREFIXES = (
    "power.",
    "media.",
    "boot.",
    "bios.",
    "firmware.",
    "storage.",
    "network.",
    "bmc.",
    "secrets.",
    "input.",
    "runtime.",
)


class TransportPolicyError(ValueError):
    """Raised when transport policy validation fails closed."""


@dataclass(frozen=True)
class TransportSecurityPolicy:
    """Validated transport defaults for future observe-only live providers."""

    connect_timeout_seconds: float = 2.0
    read_timeout_seconds: float = 5.0
    total_timeout_seconds: float = 10.0
    max_response_bytes: int = 1_048_576
    max_retries: int = 0
    tls_verify: bool = True
    allow_insecure_tls: bool = False
    allowed_methods: frozenset[str] = field(default_factory=lambda: frozenset({"GET"}))
    follow_redirects: bool = False
    expected_content_types: tuple[str, ...] = ("application/json",)

    def __post_init__(self) -> None:
        if self.connect_timeout_seconds <= 0:
            raise TransportPolicyError("connect timeout must be positive")
        if self.read_timeout_seconds <= 0:
            raise TransportPolicyError("read timeout must be positive")
        if self.total_timeout_seconds <= 0:
            raise TransportPolicyError("total timeout must be positive")
        if self.total_timeout_seconds < self.connect_timeout_seconds:
            raise TransportPolicyError("total timeout cannot be less than connect timeout")
        if self.max_response_bytes <= 0:
            raise TransportPolicyError("max response size must be positive")
        if self.max_retries < 0:
            raise TransportPolicyError("max retries cannot be negative")
        if not self.tls_verify and not self.allow_insecure_tls:
            raise TransportPolicyError("insecure TLS requires explicit override")

        normalized_methods = frozenset(method.upper() for method in self.allowed_methods)
        if not normalized_methods:
            raise TransportPolicyError("at least one method must be allowed")
        object.__setattr__(self, "allowed_methods", normalized_methods)
        object.__setattr__(
            self,
            "expected_content_types",
            tuple(str(item) for item in self.expected_content_types),
        )

    def allows_method(self, method: str) -> bool:
        """Return whether a method is allowed by policy."""

        return method.upper() in self.allowed_methods

    def should_retry(self, *, error_code: str, capability: str) -> bool:
        """Return whether a failed observe action may retry."""

        if self.max_retries <= 0:
            return False
        if not capability.startswith("observe."):
            return False
        if capability.startswith(UNSAFE_CAPABILITY_PREFIXES):
            return False
        return error_code in RETRYABLE_ERROR_CODES

    def redacted_summary(self) -> Mapping[str, Any]:
        """Return a safe policy summary for docs, CLI, MCP, and audit."""

        return MappingProxyType(
            {
                "connect_timeout_seconds": self.connect_timeout_seconds,
                "read_timeout_seconds": self.read_timeout_seconds,
                "total_timeout_seconds": self.total_timeout_seconds,
                "max_response_bytes": self.max_response_bytes,
                "max_retries": self.max_retries,
                "tls_verify": self.tls_verify,
                "allow_insecure_tls": self.allow_insecure_tls,
                "allowed_methods": sorted(self.allowed_methods),
                "follow_redirects": self.follow_redirects,
                "expected_content_types": list(self.expected_content_types),
            }
        )


__all__ = [
    "RETRYABLE_ERROR_CODES",
    "TransportPolicyError",
    "TransportSecurityPolicy",
    "UNSAFE_CAPABILITY_PREFIXES",
]
