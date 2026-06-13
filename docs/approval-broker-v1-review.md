# Approval Broker v1 Review

Branch: `feature/approval-broker-v1`

Status: implemented for development and mock-only verification. Production
trust anchors remain deferred.

## Completed

- Roadmap reset to out-of-band scope only.
- In-band remote desktop/session provider scope parked outside AgenticKVM.
- Public beta deferred behind the killer demo.
- Approval Broker v1 spec and contracts added.
- Signed approval grant model added.
- Stable parameter fingerprint binding added.
- Development/test HMAC signer added with explicit non-production limits.
- Signed grant verification added for:
  - signature
  - signer key ID
  - request ID
  - session ID
  - target
  - provider
  - capability
  - parameter fingerprint
  - risk family
  - expiry
  - one-time consumption
  - conversational channel limits
  - hard-invariant denial
- Signed approval cache added with explicit paths, atomic writes, advisory
  locking, and `0600` file mode.
- Approval request short-code and operator-message flow added.
- MCP approval tools restricted to request and deny.
- Control plane verifies signed grants before provider execution.
- Out-of-band local notifier added with Allow/Deny payload rendering.
- Operator approval CLI surface added for watch, allow, and deny.
- File-backed approval queue changed to cache/UX state only.
- Conversational approval limits documented and tested.
- MCP elicitation capability model documented with 20-second bounded wait.
- Host conformance matrix added.
- Validation now checks out-of-band roadmap scope, deferred beta language, and
  absence of MCP grant tools.

## Current Trust Model

The file-backed approval queue is no longer authority. It can record pending
requests and operator decisions, but it cannot grant provider execution.

Authority requires a broker-signed grant. The control plane verifies the grant
against the current capability request before provider execution. Unsigned,
tampered, expired, consumed, or mismatched grants fail closed.

The current HMAC signer is development/test only. It is not production authority
if the agent can read the key material. Production signer options remain:

1. keychain with user presence
2. separate-UID daemon
3. remote broker

## MCP Boundary

MCP exposes only:

- `request_approval`
- `deny_approval`

There is no MCP grant tool. Operator grant creation happens only on operator
surfaces such as the approval broker CLI, host-native elicitation, out-of-band
push channels, or a future trusted operator UI.

## Deferred

- Production signer trust anchor.
- Host-native elicitation implementation on the official Python MCP SDK.
- Network notifier implementation such as ntfy, Pushover, or Telegram.
- Live PiKVM and Redfish execution.
- Killer demo against a real wedged machine.
- Public beta launch.

## Safety Notes

- Real hardware touched: no.
- Live provider network calls made: no.
- Secrets touched: no.
- Live providers enabled: no.
- SDK trial dependency added: no.
- MCP grant tool present: no.
- Unsigned grants accepted: no.
- File queue authority removed from CLI provider execution: yes.
- Parameter fingerprint binding enforced: yes.
- Expiry enforcement: yes.
- One-time consumption enforcement: yes, for a control-plane instance.

## Follow-Up

Next recommended task: replace the development signer with a real broker trust
anchor design and then resume the official Python MCP SDK stdio server work with
elicitation capability detection.
