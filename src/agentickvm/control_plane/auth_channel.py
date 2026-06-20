"""Selectable operator authorization channel.

AgenticKVM supports two authorization channels for the clearance step:

* ``mobile_signed`` -- clearance is granted through the Agentic Control Tower
  (ACT) mobile approval flow. This is the **default** and **recommended**
  channel: approvals are signed off-device on a paired phone.
* ``local_terminal`` -- a **selectable opt-out** in which clearance is granted
  through the local signed-grant broker on the same host as the agent. It is
  less secure and less supported than ``mobile_signed`` and is warned as such.

This module only models the *selection*. It carries no risk-tiering logic --
tiering remains owned by the Tower. Routing of the clearance step by the
selected channel lives in :mod:`agentickvm.control_plane.engine`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AuthChannel(StrEnum):
    """Operator authorization channel for the clearance step."""

    MOBILE_SIGNED = "mobile_signed"
    LOCAL_TERMINAL = "local_terminal"


DEFAULT_AUTH_CHANNEL = AuthChannel.MOBILE_SIGNED
RECOMMENDED_AUTH_CHANNEL = AuthChannel.MOBILE_SIGNED

_AUTHORITY_BY_CHANNEL = {
    AuthChannel.MOBILE_SIGNED: "Agentic Control Tower",
    AuthChannel.LOCAL_TERMINAL: "local signed-grant broker",
}

LOCAL_TERMINAL_WARNING = (
    "local_terminal is a selectable opt-out: clearance is granted by the local "
    "signed-grant broker on the agent host rather than the Agentic Control Tower "
    "mobile approval. It is less secure and less supported than the recommended "
    "mobile_signed (ACT) channel; prefer mobile_signed unless you understand the "
    "trade-off."
)


@dataclass(frozen=True)
class AuthChannelSelection:
    """A resolved, validated authorization-channel selection."""

    channel: AuthChannel
    is_default: bool
    recommended: bool
    authority: str
    warning: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe, audit-friendly view of the selection."""

        return {
            "channel": self.channel.value,
            "is_default": self.is_default,
            "recommended": self.recommended,
            "authority": self.authority,
            "warning": self.warning,
        }


class AuthChannelError(ValueError):
    """Raised when an authorization-channel selection is not recognized."""


def resolve_auth_channel(
    value: AuthChannel | str | None,
    *,
    default: AuthChannel = DEFAULT_AUTH_CHANNEL,
) -> AuthChannelSelection:
    """Resolve a raw channel value into a validated selection.

    ``None`` resolves to the default (recommended) channel. Unknown values raise
    :class:`AuthChannelError` -- selection fails closed rather than silently
    falling back to a weaker channel.
    """

    if value is None:
        channel = default
    elif isinstance(value, AuthChannel):
        channel = value
    else:
        normalized = str(value).strip().lower()
        try:
            channel = AuthChannel(normalized)
        except ValueError as exc:
            allowed = ", ".join(sorted(member.value for member in AuthChannel))
            raise AuthChannelError(
                f"unknown auth_channel {value!r}; choose one of: {allowed}"
            ) from exc

    recommended = channel == RECOMMENDED_AUTH_CHANNEL
    return AuthChannelSelection(
        channel=channel,
        is_default=channel == default,
        recommended=recommended,
        authority=_AUTHORITY_BY_CHANNEL[channel],
        warning=None if recommended else LOCAL_TERMINAL_WARNING,
    )


__all__ = [
    "AuthChannel",
    "AuthChannelError",
    "AuthChannelSelection",
    "DEFAULT_AUTH_CHANNEL",
    "LOCAL_TERMINAL_WARNING",
    "RECOMMENDED_AUTH_CHANNEL",
    "resolve_auth_channel",
]
