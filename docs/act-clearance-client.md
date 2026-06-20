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
- explicit aircraft-side `risk_family` labels on clearance requests

## Contract Ownership

The canonical clearance contract is owned by ACT. Any AgenticKVM model or spec
that describes clearance request or response fields is a client-side mirror
pending alignment with the canonical ACT contract. AgenticKVM must not author a
competing clearance wire contract or invent a clearance-proof format.

AgenticKVM must not author a competing clearance wire contract. When ACT
publishes its contract, AgenticKVM alignment must be a field-mapping pass
against that authoritative source.

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

## Risk Family Labeling

AgenticKVM always sends an explicit `risk_family` in every ACT clearance
request. It does not rely on ACT to derive a missing value. Observe/read
capabilities are labeled `low_risk`; consequential capabilities such as power
cycle, force restart, HID input, virtual media, and boot-device changes are
labeled `high_risk`.

If a capability has no explicit AgenticKVM mapping, the aircraft labels it
`high_risk`. This is intentionally restrictive and avoids the permissive
default failure mode. ACT still owns channel and tier decisions, including any
mobile-mandatory requirement.

## Selectable Auth Channel

The clearance step is routed by a selected authorization channel
(`auth_channel`, default `mobile_signed`):

- `mobile_signed` clears through the ACT clearance client (the recommended,
  production path).
- `local_terminal` is a selectable opt-out that clears through the local
  signed-grant broker even if an ACT client is configured. It is warned as less
  secure and less supported, and the selection is written to the approval audit
  record.

The channel selects *which authority clears*; it does not change risk tiering,
which remains owned by the Tower. Unknown channels fail closed.

## Local Broker Work

Earlier local signed-grant broker work is superseded for production clearance
authority. It is retained as the `local_terminal` opt-out channel above and as
dev/test fixtures or compatibility tests proving that editable local files are
not authority. Production clearance comes from ACT via `mobile_signed`.

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
