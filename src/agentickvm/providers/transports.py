"""Offline provider transports for fixture-backed tests.

This module intentionally contains no live transport implementation. Future
network-capable transports must be introduced behind explicit provider specs,
manual smoke documentation, and opt-in configuration gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


class TransportError(RuntimeError):
    """Base error for offline transport failures."""


class TransportMethodNotAllowedError(TransportError):
    """Raised when a fake transport receives a disallowed method."""


class TransportRouteNotFoundError(TransportError):
    """Raised when a fake transport has no fixture for a request."""


@dataclass(frozen=True)
class TransportRequest:
    """Recorded provider transport request."""

    method: str
    path: str
    params: Mapping[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", self.method.upper())
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))


@dataclass(frozen=True)
class TransportResponse:
    """Fixture response returned by a fake transport."""

    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", MappingProxyType(dict(self.body)))

    def json(self) -> Mapping[str, Any]:
        """Return fixture body as a mapping."""

        return self.body


class FakeTransport:
    """Deterministic fixture transport.

    The transport only returns preloaded fixture mappings. It cannot discover
    hosts, open connections, or read credentials.
    """

    def __init__(
        self,
        routes: Mapping[tuple[str, str], Mapping[str, Any]],
        *,
        allowed_methods: frozenset[str] = frozenset({"GET"}),
    ) -> None:
        self.allowed_methods = frozenset(method.upper() for method in allowed_methods)
        self._routes = {
            (method.upper(), path): MappingProxyType(dict(body))
            for (method, path), body in routes.items()
        }
        self.calls: list[TransportRequest] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> TransportResponse:
        """Return a fixture response or fail closed."""

        normalized_method = method.upper()
        if normalized_method not in self.allowed_methods:
            raise TransportMethodNotAllowedError(
                f"Method {normalized_method} is not allowed by fake transport"
            )
        request = TransportRequest(
            method=normalized_method,
            path=path,
            params=params or {},
            timeout_seconds=timeout_seconds,
        )
        self.calls.append(request)
        body = self._routes.get((normalized_method, path))
        if body is None:
            raise TransportRouteNotFoundError(
                f"No fake route for {normalized_method} {path}"
            )
        return TransportResponse(status_code=200, body=body)


__all__ = [
    "FakeTransport",
    "TransportError",
    "TransportMethodNotAllowedError",
    "TransportRequest",
    "TransportResponse",
    "TransportRouteNotFoundError",
]
