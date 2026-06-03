# ADR 0001: Live Observe Transport Boundary

## Status

Proposed

## Context

AgenticKVM now has mock, PiKVM fixture, and Redfish fixture providers. The next
technical temptation is to add live observe transports. That would introduce
network access, credentials, TLS decisions, target reachability, provider
response validation, and audit obligations.

The constitution requires policy as the authority boundary, default deny,
mandatory audit, secret redaction, no real hardware in CI, and small verified
slices.

## Decision

Future live transports are allowed only after their provider-specific readiness
gates pass. They must be:

- opt-in
- disabled by default
- absent from CI
- observe-only for the first live slice
- routed through provider registry, target registry, capability request,
  `ControlPlane`, policy decision, audit, and structured result
- tested with fake transports only by default
- configured with credential references, never raw secrets

Redfish first live slice is GET-only. PiKVM first live slice is observe-only.
Mutating operations remain unimplemented or hard-denied.

## Live Transport Boundary

A live transport may only run when all are true:

- operator explicitly approves a manual smoke test
- target is an isolated lab target
- provider and target are explicitly configured
- policy mode is observe-only or narrower
- credential references are provided outside repo config
- audit path is configured
- timeout, TLS, redirect, and response validation policies are documented
- CI is not running

## Why Live Transports Are Not Implemented Yet

The repo still needs stronger conformance, transport policy, credential
reference design, and manual smoke gates before a live transport can be safe
enough to implement.

## Why Observe-Only Comes First

Observation lets the project validate provider mapping, timeout behavior, TLS
handling, audit shape, redaction, result normalization, and operator smoke
workflow without introducing power, media, boot, firmware, storage, network, or
account mutation risk.

## Fake Transport Requirements

- Unit, contract, security, and CI tests use fake transports only.
- Fake Redfish transport rejects POST, PATCH, DELETE, PUT, and action methods.
- Fake PiKVM transport supports only observe fixture routes.
- Fake transports must not read credentials or environment secrets.

## Timeout Requirements

Future live transports must define:

- connect timeout
- read timeout
- total timeout
- retry count
- retryable error set
- no retry for unsafe or mutating actions

## TLS Verification Requirements

- TLS verification defaults to true.
- Insecure TLS overrides are never default.
- Insecure TLS overrides require explicit local config, operator review, audit,
  and manual smoke scope.
- Certificate pinning may be added only through a separate spec and tests.

## Retry Policy

Retry may apply only to safe observe requests and only for retryable timeout,
connection, or rate-limit errors. Retry must not be used for authentication,
authorization, TLS verification, protocol validation, unsafe operation, or
mutation-blocked errors.

## Credential Reference Strategy

Credentials use references, not raw config. Supported future reference classes
may include keychain, strict-permission file, external vault, interactive
prompt, and manual-smoke-only environment variable references. Tests must not
resolve credential references.

## Audit Requirements

Audit must record:

- live transport attempt
- target and provider
- capability
- policy decision
- timeout/TLS policy summary
- redacted credential reference class
- provider result or structured error
- final result

## Redaction Requirements

Provider responses, credential references, URLs, headers, event logs, and screen
content must be redacted before CLI, MCP, future SDK, and audit output.

## Manual Smoke Gates

Manual smoke requires explicit operator approval, one provider, one target,
observe-only scope, config outside the repo, audit path configured, no CI, and
verification of the audit chain after the smoke.

## CI Prohibition

CI must never run live provider tests, contact BMC/KVM endpoints, read
credentials, or depend on network reachability.

## Operator Approval Requirement

The first live smoke for each provider requires human approval. Approval is not
permission to mutate, expand scope, disable audit, skip TLS review, or reuse
credentials outside the approved target.

## Rollback Strategy

- Disable the provider entry.
- Remove local credential references when no longer needed.
- Preserve audit artifacts.
- Revert local live config outside the repo.
- Do not commit local smoke config or secrets.

## Consequences

This decision slows live provider implementation but creates a safer runway for
future observe-only PiKVM and Redfish transports.

## Open Questions

- Which live provider should be attempted first?
- Should certificate pinning be mandatory before first live smoke?
- What production audit store is required before public beta?
- Which credential reference backends should be supported first?
- Should live smoke use a separate CLI command namespace?
