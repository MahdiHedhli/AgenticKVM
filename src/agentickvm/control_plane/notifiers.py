"""Out-of-band approval notifier abstractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from agentickvm.control_plane.approval_broker import BrokerApprovalRequest


@dataclass(frozen=True)
class ApprovalNotification:
    """Rendered out-of-band approval notification."""

    request_id: str
    short_code: str
    operator_message: str
    risk_summary: Mapping[str, Any]
    allow_action: Mapping[str, str]
    deny_action: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_summary", MappingProxyType(dict(self.risk_summary)))
        object.__setattr__(self, "allow_action", MappingProxyType(dict(self.allow_action)))
        object.__setattr__(self, "deny_action", MappingProxyType(dict(self.deny_action)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe notification payload."""

        return {
            "request_id": self.request_id,
            "short_code": self.short_code,
            "operator_message": self.operator_message,
            "risk_summary": dict(self.risk_summary),
            "allow_action": dict(self.allow_action),
            "deny_action": dict(self.deny_action),
        }


class ApprovalNotifier(Protocol):
    """Notifier interface for out-of-band approval channels."""

    def notify(self, request: BrokerApprovalRequest) -> ApprovalNotification:
        """Render or send a notification for an approval request."""


@dataclass
class LocalApprovalNotifier:
    """Local test notifier that records Allow/Deny payloads without network."""

    sent: list[ApprovalNotification] = field(default_factory=list)

    def notify(self, request: BrokerApprovalRequest) -> ApprovalNotification:
        """Render an Allow/Deny notification and keep it in memory."""

        notification = ApprovalNotification(
            request_id=request.request_id,
            short_code=request.short_code.value,
            operator_message=request.operator_message,
            risk_summary=request.risk_summary.to_dict(),
            allow_action={
                "label": "Allow",
                "action": "allow",
                "request_id": request.request_id,
                "short_code": request.short_code.value,
            },
            deny_action={
                "label": "Deny",
                "action": "deny",
                "request_id": request.request_id,
                "short_code": request.short_code.value,
            },
        )
        self.sent.append(notification)
        return notification
