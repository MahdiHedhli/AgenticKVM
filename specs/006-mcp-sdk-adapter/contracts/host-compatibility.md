# MCP Host Compatibility Contract

## Status

Mock-only, dependency-free contract. This is not a live MCP server contract.

## Purpose

The host compatibility layer models how a future external MCP host should
interact with AgenticKVM before a real MCP SDK dependency or server transport is
introduced.

It is a local, in-memory boundary for tests and demos. It proves that host-style
requests cannot bypass the existing adapter, router, registries, policy engine,
approval handling, provider contract, or audit path.

## Required Flow

Every host tool call must follow this path:

```text
host-style request
-> MCP SDK compatibility adapter
-> MCP router
-> provider registry
-> target registry
-> capability registry
-> ControlPlane
-> approval if required
-> provider adapter only if allowed
-> audit event
-> structured host result
```

The host compatibility layer must not call providers directly.

## Exposed Operations

The layer may expose only local methods for:

- list tools
- get tool schema
- call tool
- serialize result
- serialize error

It must not open a network listener, import a live MCP SDK, start a daemon,
accept remote connections, or act as an authority boundary.

## Safety Requirements

- mock-only configuration is the default
- real providers are disabled by default
- credential references are not resolved
- environment secrets are not read
- unknown tools fail closed
- unknown targets fail closed
- disabled providers and targets fail closed
- approval-required results are first-class outcomes
- gated actions are never auto-approved
- raw exceptions are not exposed to callers
- outputs are JSON-safe
- secret-like fields are redacted
- provider errors are serialized into structured host errors
- schemas do not include live hostnames, IP addresses, credentials, tokens, or
  secret examples

## Tool Schema Contract

Tool schemas must include:

- tool name
- mapped capability
- description
- dangerous-action flag if known
- required inputs
- possible result statuses

Tool schemas must not include provider internals, credential examples, real
targets, real hostnames, real IP addresses, or instructions for live provider
access.

## Result Statuses

Host results must preserve the SDK adapter statuses:

- `ok`
- `denied`
- `approval_required`
- `validation_error`
- `provider_error`
- `policy_error`

`approval_required` is not a failure and is not permission to continue. A
future host must surface the approval request without auto-approving it.

## Future Real MCP SDK Gate

A future real MCP SDK or server adapter must conform to this contract before it
can be used with live provider work. The real adapter must prove that it:

- routes through this same authority path
- does not bypass policy
- does not enable real providers by default
- does not resolve credentials by default
- does not expose raw secrets
- does not add live-network tests to CI

## Live Server Conformance Checklist

Before a real MCP SDK/server adapter is accepted, it must pass the mock host
compatibility suite and preserve these behaviors exactly:

- tool listing remains JSON-safe and contains no live targets or credentials
- tool schemas remain JSON-safe and contain no live hostnames, IPs, credentials,
  tokens, cookies, or provider bypass instructions
- every tool call routes through `MCPSDKAdapter`, `MCPRouter`, provider
  registry, target registry, capability registry, and `ControlPlane`
- no host path calls a provider directly
- unknown tools, unknown targets, disabled providers, disabled targets, and
  provider/target mismatches fail closed
- `approval_required` remains a first-class result
- the host never auto-approves
- approval responses must match request id, session, target, provider,
  capability, parameter fingerprint, scope, and expiry
- one-time and session approval semantics remain unchanged
- approval resumption still routes through `ControlPlane`
- provider errors remain structured, redacted, and retry metadata is preserved
- approval resumption does not hide provider errors
- audit persistence remains redacted and hash-chain verifiable
- audit tampering, middle-event deletion, and reordering are detected by the
  current verification helper
- artifact results expose metadata only and never raw bytes
- golden host result fixtures still match generated host output
- host result schema validation rejects unsafe shapes, raw bytes, exception
  objects, unknown statuses, and unredacted sensitive keys
- mock-only mode remains available and is the default in CI
- live providers, live network access, and credential resolution remain disabled
  unless explicitly approved by a later readiness gate
