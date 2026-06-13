# ACT Client Boundary

Canonical source: Agentic Control Tower. AgenticKVM consumes ACT clearance and
mirrors only the client-side expectations needed to build the seam before ACT's
canonical contract is published.

## Boundary

- AgenticKVM requests clearance from ACT.
- ACT owns the clearance contract, signing, mobile operator channel, replay
  defense, one-time clearance consumption, and clearance audit.
- AgenticKVM verifies returned clearance as a tower client.
- AgenticKVM does not sign or clear requests itself.
- AgenticKVM does not expose grant, approve, clear, sign, or trust-signer tools
  over MCP.
- AgenticKVM fails closed when ACT is unavailable or verification fails, unless
  policy explicitly allows returning `clearance_required`.

## Timeout

The default maximum wait is 20 seconds. Tool calls must return rather than block
indefinitely.
