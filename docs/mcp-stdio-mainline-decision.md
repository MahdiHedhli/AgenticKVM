# MCP Stdio Mainline Decision

## Status

Deferred.

The mock-only MCP stdio work remains on the Python MCP SDK trial branch. This
integration branch does not add the SDK dependency, does not port the trial
adapter, and does not add an `agentickvm-mcp` entry point.

## Reason

The SDK trial is promising but not ready for mainline adoption. Open gates:

- lockfile or constraints strategy
- dependency footprint review
- SDK logging review
- optional extras policy
- production audit backend decision
- live transport decision
- human security review

## Current Mainline Boundary

Mainline keeps:

- dependency-free `MCPSDKAdapter`
- dependency-free `MCPHostCompatibilityLayer`
- mock-only host conformance tests
- no live MCP server default
- no SDK dependency in `pyproject.toml`

## Future Acceptance Gate

A future stdio PR must:

- wrap `MCPHostCompatibilityLayer`
- preserve `MCPRouter`, registries, and `ControlPlane`
- preserve `approval_required`
- not auto-approve
- not call providers directly
- not enable real providers by default
- not open network listeners
- pass all host conformance, approval, audit, provider-error, and artifact tests
- keep CI mock-only
