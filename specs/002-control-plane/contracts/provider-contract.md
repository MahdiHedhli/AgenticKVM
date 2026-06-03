# Provider Adapter Contract

Provider adapters are execution adapters. They are not authority boundaries and
must not own policy.

## Required Responsibilities

A provider adapter must:

- expose a stable provider id and provider kind
- declare supported provider-neutral capability ids
- accept only already-authorized capability requests
- translate provider-neutral requests into provider-specific operations
- return structured results
- redact secrets by default
- expose whether it can touch real hardware
- fail closed on malformed authorized requests

## Prohibited Responsibilities

A provider adapter must not:

- decide visible control mode
- grant or deny policy
- request operator approval
- widen target or session scope
- add credentials silently
- reveal raw secrets by default
- erase or suppress audit events
- treat provider-specific reset, boot, firmware, or storage actions as low risk

## Required Call Boundary

Provider adapters may be called only by the control plane after:

1. capability registry resolution
2. policy decision
3. approval if required
4. audit event for request and decision

MCP tools, CLI commands, API handlers, and agent workflows must not call
providers directly.

## Bootstrap Mock Provider

The bootstrap mock provider is safe by construction:

- `is_real_hardware` is false
- no network or device calls are made
- actions are recorded as mock observations
- results must be marked as mock and not performed on hardware
