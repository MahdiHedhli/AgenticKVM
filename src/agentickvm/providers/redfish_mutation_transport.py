"""Redfish live MUTATION transport boundary.

This is the separate explicit mutating path next to the structurally GET-only
``redfish_transport`` read seam. It is socket-free by injection: the TLS probe
and the POST/PATCH-capable HTTP client are injected, and the only real network
implementations live in ``agentickvm.live_validation`` for operator-run
sessions. Automated tests exercise this seam exclusively with fakes.

Every mutating verb requires, fail-closed:

- a pinned certificate fingerprint (no pin -> refused at construction),
- a passed TLS pin preflight (mismatch -> refused before credentials exist),
- a ``VerifiedMutationClearance`` handle bound to this capability, target,
  provider, and params fingerprint (missing/mismatched/expired/replayed ->
  refused before any client is built or credential resolved).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Callable, Protocol

from agentickvm.providers.errors import (
    ProviderMutationBlockedError,
    ProviderProtocolError,
)
from agentickvm.providers.mutation_gate import (
    MutationClearanceLedger,
    VerifiedMutationClearance,
    require_verified_mutation_clearance,
)
from agentickvm.providers.pikvm_transport import normalize_cert_fingerprint
from agentickvm.providers.redfish_transport import (
    RedfishCredentialRef,
    RedfishFingerprintMismatchError,
    RedfishPinnedTrust,
    RedfishTargetConfig,
    RedfishTLSProbe,
    redact_redfish_read_payload,
)
from agentickvm.providers.transport_policy import TransportSecurityPolicy
from agentickvm.providers.transports import TransportError

# The only mutating verbs this transport implements. Everything else
# (bmc.reset, NMI, graceful variants, media, firmware) remains unimplemented
# and therefore unreachable through the live layer.
REDFISH_LIVE_MUTATING_OPERATIONS = frozenset(
    {
        "power.on",
        "power.force_off",
        "power.power_cycle",
        "boot.override",
    }
)

# AgenticKVM power capability -> Redfish ComputerSystem.Reset ResetType.
_REDFISH_RESET_TYPES = {
    "power.on": "On",
    "power.force_off": "ForceOff",
    "power.power_cycle": "PowerCycle",
}

# Conservative one-time boot override target allowlist.
REDFISH_BOOT_OVERRIDE_TARGETS = frozenset(
    {"None", "Pxe", "Hdd", "Cd", "Usb", "BiosSetup"}
)

COMPUTER_SYSTEM_RESET_ACTION_SUFFIX = "/Actions/ComputerSystem.Reset"


class RedfishHTTPMutationClient(Protocol):
    """POST/PATCH-capable client built per actuation after every gate passes."""

    trust: RedfishPinnedTrust

    def post_json(
        self, path: str, body: Mapping[str, Any], *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        """Perform a mutating POST and return the JSON response object."""

    def patch_json(
        self, path: str, body: Mapping[str, Any], *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        """Perform a mutating PATCH and return the JSON response object."""


RedfishMutationHTTPClientFactory = Callable[
    [
        RedfishTargetConfig,
        RedfishCredentialRef,
        RedfishPinnedTrust,
        VerifiedMutationClearance,
    ],
    RedfishHTTPMutationClient,
]


class LiveRedfishMutationTransport:
    """Clearance-gated Redfish mutation transport built after pin preflight.

    The mutating HTTP client is built per actuation call, only after the
    per-call clearance gates pass, so credentials are never resolved for a
    refused mutation.
    """

    def __init__(
        self,
        *,
        config: RedfishTargetConfig,
        credential_ref: RedfishCredentialRef,
        target_id: str,
        provider_id: str,
        system_path: str,
        tls_probe: RedfishTLSProbe,
        http_client_factory: RedfishMutationHTTPClientFactory,
        ledger: MutationClearanceLedger | None = None,
        policy: TransportSecurityPolicy | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        if not config.cert_fingerprint:
            raise ProviderMutationBlockedError(
                "mutating Redfish transport requires a pinned certificate "
                "fingerprint; no pin means no mutation"
            )
        if not target_id or not provider_id:
            raise ProviderMutationBlockedError(
                "mutating Redfish transport requires target and provider identity"
            )
        self._system_path = _validated_system_path(system_path)
        self.config = config
        self.credential_ref = credential_ref
        self.target_id = target_id
        self.provider_id = provider_id
        self.policy = policy or TransportSecurityPolicy(
            read_timeout_seconds=config.read_timeout_seconds,
            connect_timeout_seconds=config.connect_timeout_seconds,
            tls_verify=config.verify_ssl,
            allow_insecure_tls=not config.verify_ssl and bool(config.cert_fingerprint),
        )
        self._ledger = ledger or MutationClearanceLedger()
        self._now_factory = now_factory or (lambda: datetime.now(UTC))
        self._http_client_factory = http_client_factory
        self._trust = self._preflight_pin(tls_probe)

    # -- mutating verbs ------------------------------------------------------

    def power_on(self, *, clearance: object) -> Mapping[str, Any]:
        """Power the system on via ComputerSystem.Reset (clearance-gated)."""

        return self._reset("power.on", clearance)

    def power_force_off(self, *, clearance: object) -> Mapping[str, Any]:
        """Force the system off via ComputerSystem.Reset (clearance-gated)."""

        return self._reset("power.force_off", clearance)

    def power_cycle(self, *, clearance: object) -> Mapping[str, Any]:
        """Power-cycle the system via ComputerSystem.Reset (clearance-gated)."""

        return self._reset("power.power_cycle", clearance)

    def set_boot_override(
        self, *, boot_target: str, clearance: object
    ) -> Mapping[str, Any]:
        """Set a one-time boot-source override (clearance-gated)."""

        if boot_target not in REDFISH_BOOT_OVERRIDE_TARGETS:
            raise ProviderMutationBlockedError(
                "boot override target is outside the supported allowlist"
            )
        parameters = {"boot_target": boot_target}
        verified = self._authorize("boot.override", parameters, clearance)
        payload = self._mutate(
            "PATCH",
            self._system_path,
            {
                "Boot": {
                    "BootSourceOverrideTarget": boot_target,
                    "BootSourceOverrideEnabled": "Once",
                }
            },
            verified,
        )
        return self._summary("boot.override", payload)

    # -- internals -----------------------------------------------------------

    def _reset(self, capability: str, clearance: object) -> Mapping[str, Any]:
        verified = self._authorize(capability, {}, clearance)
        payload = self._mutate(
            "POST",
            self._system_path + COMPUTER_SYSTEM_RESET_ACTION_SUFFIX,
            {"ResetType": _REDFISH_RESET_TYPES[capability]},
            verified,
        )
        return self._summary(capability, payload)

    def _authorize(
        self,
        capability: str,
        parameters: Mapping[str, Any],
        clearance: object,
    ) -> VerifiedMutationClearance:
        if capability not in REDFISH_LIVE_MUTATING_OPERATIONS:
            raise ProviderMutationBlockedError(
                "Redfish live mutation transport does not implement this verb"
            )
        return require_verified_mutation_clearance(
            clearance,
            capability=capability,
            parameters=parameters,
            target=self.target_id,
            provider=self.provider_id,
            now=self._now_factory(),
            ledger=self._ledger,
        )

    def _mutate(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any],
        verified: VerifiedMutationClearance,
    ) -> Mapping[str, Any]:
        client = self._http_client_factory(
            self.config, self.credential_ref, self._trust, verified
        )
        try:
            if method == "POST":
                return client.post_json(
                    path, body, timeout_seconds=self.policy.read_timeout_seconds
                )
            return client.patch_json(
                path, body, timeout_seconds=self.policy.read_timeout_seconds
            )
        except TransportError as exc:
            raise ProviderProtocolError("Redfish live mutation transport error") from exc

    def _summary(
        self, capability: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "capability": capability,
                "performed": True,
                "response": redact_redfish_read_payload(dict(payload)),
            }
        )

    def _preflight_pin(self, tls_probe: RedfishTLSProbe) -> RedfishPinnedTrust:
        expected = normalize_cert_fingerprint(self.config.cert_fingerprint)
        observed = normalize_cert_fingerprint(
            tls_probe.certificate_der_sha256(
                host=self.config.host,
                port=self.config.port,
                timeout_seconds=self.config.connect_timeout_seconds,
            )
        )
        if observed != expected:
            raise RedfishFingerprintMismatchError(
                "Redfish certificate fingerprint mismatch; credentials were not sent"
            )
        return RedfishPinnedTrust(expected)


def _validated_system_path(system_path: str) -> str:
    if (
        not system_path
        or not system_path.startswith("/redfish/")
        or ".." in system_path
        or "?" in system_path
        or "#" in system_path
    ):
        raise ProviderProtocolError(
            "Redfish mutation transport requires an absolute /redfish/ system path"
        )
    return system_path.rstrip("/")


__all__ = [
    "COMPUTER_SYSTEM_RESET_ACTION_SUFFIX",
    "LiveRedfishMutationTransport",
    "REDFISH_BOOT_OVERRIDE_TARGETS",
    "REDFISH_LIVE_MUTATING_OPERATIONS",
    "RedfishHTTPMutationClient",
    "RedfishMutationHTTPClientFactory",
]
