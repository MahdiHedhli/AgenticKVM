# Transport Security

AgenticKVM now includes a PiKVM live transport foundation, but it is not enabled
by default and automated tests still use mocks only. This document defines the
policy live transports must satisfy.

## Defaults

- TLS verification defaults to true.
- Insecure TLS is never default.
- Redfish first live slice is GET-only.
- PiKVM first live slice is observe-only.
- Redirects are disabled unless a provider spec explicitly allows them.
- Tests use fake transports only.
- PiKVM fixture tests use `FakePiKVMObserveTransport`.
- PiKVM cert-pinning tests use injected mock TLS/HTTP layers; no automated test
  calls a live PiKVM.

## Timeouts

The policy model defines:

- connect timeout
- read timeout
- total timeout
- maximum response size

Invalid timeout values fail closed.

## Retry

Retries are allowed only for safe observe requests and only for retryable
network/provider availability errors. Unsafe or mutating actions are never
retried.

## TLS

An insecure TLS override must be explicit, manual, audited, and never default.
For self-signed PiKVM deployments, `verify_ssl=false` is acceptable only when a
`cert_fingerprint` is configured and verified before credentials are sent.

PiKVM certificate pinning uses a preflight:

1. Open an unauthenticated TLS connection.
2. Compute the presented certificate SHA-256 fingerprint.
3. Compare it with the configured `cert_fingerprint`.
4. Abort before credential use on mismatch.
5. Only on match, construct the authenticated client and trust the pinned
   certificate as the sole trust root.

This is why `verify_ssl=false` can be intentional for self-signed PiKVM only
when paired with pinning. Without pinning, it is a misconfiguration.

## Redfish And PiKVM

- Redfish first-slice methods: `GET` only.
- PiKVM first-slice behavior: observe-only, no input or mutation.
- PiKVM live observe transport foundation exists for observe-class calls only:
  health/status, screen/screenshot metadata, ATX power-state read, boot status,
  and device info. It uses injectable TLS/HTTP adapters in tests and is not
  enabled by default.
- PiKVM screenshot observations are sensitive artifacts; audit records metadata
  only and must not include raw image bytes.

## Audit

Future live network attempts must emit audit events that include redacted
transport policy summary, method, capability, provider, target, TLS policy, and
timeout policy.

## Current Implementation

`TransportSecurityPolicy` validates defaults and retry decisions. It does not
resolve credentials or approve live provider use.

`FakePiKVMObserveTransport` accepts the policy object for future boundary
compatibility, but it still performs no network IO.

`LivePiKVMObserveTransport` is a foundation with injected TLS probe and HTTP
client factory. Tests prove fingerprint mismatch aborts before credentials are
handed to the authenticated client factory.
