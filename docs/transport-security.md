# Transport Security

AgenticKVM does not implement live provider transports yet. This document
defines the policy future transports must satisfy.

## Defaults

- TLS verification defaults to true.
- Insecure TLS is never default.
- Redfish first live slice is GET-only.
- PiKVM first live slice is observe-only.
- Redirects are disabled unless a provider spec explicitly allows them.
- Tests use fake transports only.

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
It is not available in tests.

## Redfish And PiKVM

- Redfish first-slice methods: `GET` only.
- PiKVM first-slice behavior: observe-only, no input or mutation.

## Audit

Future live network attempts must emit audit events that include redacted
transport policy summary, method, capability, provider, target, TLS policy, and
timeout policy.
