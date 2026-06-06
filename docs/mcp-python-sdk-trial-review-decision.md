# Python MCP SDK Trial Review Decision

## Status

Decision: continue trial, hold mainline adoption.

This integration branch does not add `mcp==1.27.2`, does not merge
`trial/mock-only-mcp-python-sdk`, and does not adopt a live MCP server.

## Reviewed Sources

Reviewed from `trial/mock-only-mcp-python-sdk` without merging:

- `docs/mcp-python-sdk-trial-plan.md`
- `docs/mcp-python-sdk-trial-security-review.md`
- `docs/mcp-python-sdk-adoption-proposal.md`
- `docs/mcp-python-sdk-trial-risk-report.md`
- `docs/mcp-python-sdk-stdio-smoke-report.md`
- `src/agentickvm/mcp_sdk/python_sdk_server.py`
- `src/agentickvm/mcp_sdk/python_sdk_stdio.py`
- trial `pyproject.toml`

## What The Trial Proves

The trial branch provides useful evidence:

- `mcp==1.27.2` imports in the trial environment.
- `FastMCP` can be constructed without socket creation in tests.
- The trial adapter wraps `MCPHostCompatibilityLayer`.
- SDK handlers do not call providers directly.
- In-memory list/call tests pass.
- Stdio-shaped JSON-line replay passes on the trial branch.
- Approval-required, denied, provider-error, audit, and artifact cases are
  preserved in mock-only tests.
- No listener is started by the trial harness.
- No live providers are enabled.

## Blocking Issues For Mainline Adoption

Mainline adoption remains blocked by:

- dependency footprint includes HTTP/server-capable packages
- `uv.lock` strategy remains unresolved
- SDK live transport logging remains unreviewed
- optional extras are disallowed for now but not fully reviewed
- real SDK stdio transport is not adopted
- live MCP server transport remains undecided
- production audit backend remains undecided
- human review is still required

## Decision

Do not port SDK code or dependency into this integration branch.

Move 3, mainline mock-only MCP stdio server, is deferred until a human reviewer
accepts:

- dependency version strategy
- lockfile or constraints strategy
- logging behavior review
- optional extras policy
- production audit backend direction
- live MCP server transport boundary
- mainline security review

## Permitted Follow-Up

Safe follow-up work may include docs-only planning for eventual adoption and
additional dependency review. Code porting from the trial branch requires a
separate explicit adoption decision.

## Safety Assertion

This branch keeps the dependency-free `MCPSDKAdapter` and
`MCPHostCompatibilityLayer` as the mainline MCP readiness boundary. No live MCP
server is enabled by default, and no SDK dependency is present in
`pyproject.toml`.
