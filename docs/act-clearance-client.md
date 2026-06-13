# ACT Clearance Client

AgenticKVM is now a client aircraft of Agentic Control Tower, abbreviated ACT.

ACT grants or denies clearance. AgenticKVM flies the plane.

## Authority Boundary

AgenticKVM consumes ACT clearance. It does not own production approval signing,
mobile operator surfaces, grant authority, one-time clearance consumption, replay
defense crypto, or the clearance audit chain.

ACT owns:

- clearance request and response contract
- clearance proof/signature format
- Ed25519 full-request signing
- parameter fingerprints
- one-time clearance consumption
- replay defense
- mobile operator approval
- local-terminal fallback approval
- tower-side clearance audit

AgenticKVM owns:

- capability resolution
- local policy decisions
- provider and target registries
- fail-closed behavior
- provider execution
- local structured audit
- PiKVM and Redfish provider transport work
- recovery workflows

## Contract Ownership

The canonical clearance contract is owned by ACT. Any AgenticKVM model or spec
that describes clearance request or response fields is a client-side mirror
pending alignment with the canonical ACT contract. AgenticKVM must not author a
competing clearance wire contract or invent a clearance-proof format.

When ACT publishes its contract, AgenticKVM alignment must be a field-mapping
pass against that authoritative source.

## Clearance Flow

```text
AgenticKVM policy says clearance is required
-> AgenticKVM builds an ACT clearance request mirror
-> AgenticKVM calls ACT through a bounded client timeout
-> ACT returns clearance_required, denied, cleared, or a failure state
-> AgenticKVM verifies the tower response through the ACT client seam
-> AgenticKVM proceeds only on verified cleared response
-> AgenticKVM audits local request, policy, clearance result, and provider result
```

If ACT is unavailable or the response cannot be verified, AgenticKVM fails
closed or returns `clearance_required` where policy explicitly allows waiting
for out-of-band operator action.

## Local Broker Work

Earlier local signed-grant broker work is superseded for production clearance
authority. Local signing and cache scaffolds may remain only as dev/test
fixtures or compatibility tests proving that editable local files are not
authority. Production clearance comes from ACT.

## MCP Surface

MCP may expose only:

- `request_clearance`
- `deny_clearance`

MCP must never expose grant, approve, clear, sign, or trust-signer tools.
Granting and clearing live only on ACT operator surfaces such as phone approval,
local-terminal fallback, or a future trusted operator UI.

## Timeout Rule

No tool call may block indefinitely while waiting for human approval. The
default maximum wait is 20 seconds and must remain configurable. If the operator
has not caught up, AgenticKVM returns `clearance_required` with a short code,
risk summary, `operator_message`, and retry guidance.
