# Conversational Approval Policy

Conversational approval is not a trusted operator channel. A model can repeat,
misread, or fabricate chat content, and an agent with tool access may influence
its own transcript. AgenticKVM therefore treats conversational approval as
unverified unless a broker signs a grant and the control plane verifies the
exact request binding.

Conversational approval is allowed only for explicitly flagged low-risk risk
families such as observe-only and runtime metadata flows. It is never the
default approval channel.

## Banned Families

Conversational approval cannot authorize:

- power
- input
- boot
- media
- provider mutation
- credential changes
- policy changes
- audit changes
- emergency stop changes

These families require an operator surface backed by a broker signer, such as a
host-native elicitation dialog, an out-of-band notifier, the approval watch
command, or a future trusted operator UI.

## Audit

If conversational approval is accepted for a low-risk family, the event must be
audited with `conversational_unverified`. The grant must still carry the normal
signed grant binding:

- request ID
- session ID
- target
- provider
- capability
- parameter fingerprint
- risk family
- expiry
- one-time or session scope

## Control-Plane Rule

Conversational text alone never grants execution. The control plane accepts
only a signed broker grant that verifies against the current request. Hard
invariants remain denied even when a conversational grant is signed.
