# ADR 0002: PiKVM Live Observe Transport

## Status

Proposed

## Context

AgenticKVM has a fixture-backed PiKVM observe provider, provider conformance
tests, transport security policy scaffolding, credential reference validation,
and manual smoke gates. The next safe step is to define the PiKVM live observe
transport boundary before any live network client exists.

The constitution requires policy as the authority boundary, default deny,
mandatory audit, secret redaction, no real hardware in CI, and small verified
slices. PiKVM can expose screen and device state for machines whose operating
system may be offline, but the same interface family can also support input,
power, media, and boot operations. Those mutating operations remain out of
scope for the first live slice.

## Selected First Provider

PiKVM observe-only is the selected first provider-specific live transport
design target.

## Why PiKVM First

- PiKVM is close to the original donor-spike experience without making the
  donor architecture authoritative.
- Screen observation is a high-value out-of-band capability that exercises
  artifact sensitivity, redaction, provider result normalization, audit, and
  operator smoke workflow.
- The fixture-backed PiKVM provider already has a safe test lane that can be
  hardened before any live client code is introduced.

## Why Observe-Only First

Observe-only work validates provider mapping, timeout policy, TLS policy,
credential reference shape, redaction, audit output, screenshot sensitivity,
and CLI/MCP routing without introducing state-changing machine control.

## Decision

This lane defines and tests the PiKVM observe transport boundary with fake
transports only. It does not implement a live network transport.

Future PiKVM live observe transport may be implemented only after the manual
smoke gate is complete and all real-provider readiness gates still pass. All
future live execution must flow through:

1. CLI, MCP, or future SDK request
2. provider registry
3. target registry
4. capability request
5. `ControlPlane`
6. policy decision
7. approval if required
8. provider adapter
9. audit event
10. structured result

No external interface may call PiKVM transport or provider methods directly.

## Why Live Transport Is Not Implemented In This Lane

Live transport would require network access, reachable PiKVM hardware,
credential resolution, TLS decisions against a real endpoint, screenshot
artifact handling, and manual operator approval. Those are intentionally
excluded from this offline repo-local sprint.

This lane only adds:

- provider-specific ADR
- fake-only transport interface
- fixture contracts
- config and artifact safety checks
- CLI/MCP fixture coverage
- manual smoke design updates

## Allowed Future Live Observe Capabilities

- `observe.screen`
- `observe.screenshot`, only when explicitly scoped and artifact handling is
  configured
- `observe.power_state`, only if the PiKVM endpoint exposes safe read behavior
- `observe.boot_status`, only when inferable without mutation
- provider health/status

## Explicitly Disallowed Live Capabilities

- keyboard input
- mouse input
- paste
- power actions
- reset actions
- virtual media
- boot changes
- storage changes
- network changes
- credential changes
- `POST`, `PUT`, `PATCH`, or `DELETE` unless a later provider-specific spec
  proves a read-only endpoint and adds tests
- any action requiring real machine mutation

## Transport Injection Model

PiKVM provider code must receive a transport object through explicit
construction. Tests use a fake transport only. Default construction must not
create a live network transport.

Future live transport construction must be gated by explicit local config,
disabled by default, absent from CI, and unavailable to tests unless a fake
transport is injected.

## Fake Transport Requirements

- Uses deterministic fixture responses.
- Supports observe-only methods.
- Rejects unknown endpoints and mutating methods.
- Performs no DNS, socket, HTTP, file credential, or environment secret access.
- Records requests for tests.
- Normalizes errors through the provider error taxonomy.

## Future Live Transport Requirements

- Explicit operator config outside the repo.
- Credential references, never raw credentials.
- Credential references resolved only by an approved future backend.
- TLS verification on by default.
- Insecure TLS override unavailable by default and documented as a manual-smoke
  exception only.
- Bounded connect, read, and total timeouts.
- No unsafe retries.
- Response size limits.
- Strict response shape validation.
- Redaction before CLI, MCP, SDK, audit, and logs.
- Audit events for every attempted provider execution.

## Timeout Policy

Future live transport must accept a validated timeout policy with connect,
read, and total timeout values. Defaults remain short and fail closed. Timeout
errors normalize to the provider error taxonomy and may be retryable only for
safe observe requests.

## TLS Verification Policy

TLS verification defaults to true. Insecure TLS is not a default, not allowed
in examples as enabled live config, and requires an explicit future manual
smoke decision. Certificate pinning remains an open question for live smoke.

## Credential Reference Strategy

PiKVM config may contain a `credential_ref` value, but this repository does not
resolve it in tests or fixture mode. Raw passwords, tokens, cookies, bearer
values, private keys, and credential material remain rejected by config
validation.

## Screenshot And Screen Sensitivity Policy

Screen observations and screenshots may expose passwords, console sessions,
installation keys, hostnames, IP addresses, and customer data. Live screenshot
capture therefore requires explicit target scope, artifact path, audit path,
redaction policy, and operator approval when policy requires it.

Tests should use synthetic metadata or tiny fake fixtures only. Screenshots
must not be committed to the repository.

## Artifact Storage Policy

Screenshot artifacts are sensitive. Artifact output must be explicit, must not
default into tracked repo paths, and should avoid embedding target names in
filenames. Audit logs record artifact metadata, not raw image bytes.

## Redaction Policy

PiKVM transport output must redact credential references, URLs that could
include credentials, headers, cookies, target-sensitive names, screenshot raw
bytes, and secret-like response fields before any external result or audit
write.

## Audit Policy

Audit must record:

- provider id and target id
- capability
- policy decision
- approval state if applicable
- transport policy summary
- credential reference class only
- fixture/live mode marker
- provider result or normalized error
- artifact metadata only

Audit must never include raw credentials or raw screenshot bytes.

## Manual Smoke Gate

Future live smoke requires:

- explicit human approval
- isolated lab PiKVM target
- observe-only scope
- local config outside this repo
- credential reference outside this repo
- audit path configured
- artifact path configured
- TLS and timeout policy reviewed
- no CI execution
- preflight confirmation that mutating tools remain unavailable

## CI Prohibition

CI must never run PiKVM live smoke, contact PiKVM endpoints, resolve
credentials, depend on network reachability, write live screenshots, or operate
real hardware.

## Rollback And Cleanup

- Disable the local PiKVM provider entry.
- Remove local credential references when no longer needed.
- Preserve audit artifacts.
- Remove local screenshot artifacts according to the smoke checklist.
- Do not commit local smoke config, credentials, screenshots, or endpoint
  details.

## Open Questions

- Should live PiKVM screenshot capture require approval even in Observe mode?
- Should certificate pinning be required before first live smoke?
- Which credential backend should resolve PiKVM credential references first?
- What exact PiKVM endpoint set should be used for the first live smoke?
- Should screenshot artifacts use content-addressed names or randomized names?
