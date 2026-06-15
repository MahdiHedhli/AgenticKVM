# MCP Elicitation Capability Detection Contract

Status: proposed

Future live MCP SDK adapters must detect host-native elicitation support during
MCP initialization before attempting to render an approval prompt in the host.

## Requirements

- Detect elicitation capability at initialize time.
- Treat Claude Desktop as the best-case reference host when elicitation is
  available.
- Treat Claude Code as the worst-case reference host when elicitation is absent
  or unreliable.
- Do not add host-specific bypasses around the published host conformance
  contract.
- Do not block a tool call indefinitely while waiting for elicitation.
- Default maximum approval wait is 20 seconds.
- The timeout must be configurable by explicit policy, not by hidden host
  behavior.
- If elicitation is unavailable or does not complete before timeout, return
  `approval_required`.
- The fallback result must include a short code, operator message, risk summary,
  and retry instructions for out-of-band approval.
- Native elicitation approval must still produce a broker-signed grant.
- The control plane must verify the signed grant before provider execution.

## Non-Goals

- No bespoke host-specific approval implementation in this contract.
- No MCP grant tool.
- No indefinite wait for a host dialog.
- No provider execution based on conversational text alone.

## Test Expectations

Mock host compatibility tests must prove:

- initialize metadata can represent elicitation present or absent
- approval timeout returns `approval_required`
- out-of-band fallback preserves the original request fingerprint
- no host path can bypass `MCPRouter` or `ControlPlane`
