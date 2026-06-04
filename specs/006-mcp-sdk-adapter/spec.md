# Specification: MCP SDK Adapter

## Status

Mock-only internal adapter scaffold implemented. No live MCP SDK server is
implemented in this spec.

## Goal

Define the future MCP SDK adapter as a thin translation layer over the existing
MCP router.

## Scope

In scope:

- SDK adapter boundary
- mock-only first adapter plan
- dependency-free internal adapter scaffold
- dependency-free local host compatibility layer
- JSON-safe result contract
- approval-required result behavior
- mock-only host approval response and resumption behavior
- host audit persistence behavior
- no provider bypass rule

Out of scope:

- SDK dependency selection
- live MCP client tests
- live provider execution
- credential loading
- approval transport UI

## Requirements

- MCP SDK adapter is not an authority boundary.
- Adapter routes to the existing `MCPRouter`.
- Adapter cannot call providers directly.
- Mock-only first.
- No real providers by default.
- No credentials.
- Unknown tools fail closed.
- Unknown targets fail closed.
- Structured `approval_required` results remain first-class.
- Results must be JSON-safe and secret-redacted.
- Host compatibility calls must route through `MCPSDKAdapter`.
- Host compatibility schemas must be JSON-safe and must not include secrets,
  live targets, live hostnames, or provider bypass details.
- Host approval responses must bind to session, target, provider, capability,
  params fingerprint, scope, and expiry.
- Host approval resumption must still route through `ControlPlane`.
- Host-compatible audit persistence must use explicit local paths, redact
  secrets, and preserve hash-chain verification.
- The current adapter must remain dependency-free until the real SDK decision
  is reviewed.
