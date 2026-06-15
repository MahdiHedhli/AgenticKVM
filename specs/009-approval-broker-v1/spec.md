# Approval Broker v1 Specification

## Purpose

Approval Broker v1 makes operator approval a real trust boundary. The broker
owns approval state, signs every grant, and the control plane verifies signed
grants before provider execution.

Editable files are not authority. Local storage is cache only.

## Goals

- Signed grants are the approval authority.
- ControlPlane verifies grants before approved provider execution.
- Grants bind to the exact original request shape.
- Out-of-band operator approval is the default trust anchor.
- MCP can request approval and deny approval, but cannot grant approval.
- Tool calls do not block indefinitely and default to a maximum 20 second wait.
- Storage uses atomic writes, advisory locking, and mode `0600`.
- Development signers are clearly separated from production trust anchors.

## Non-Goals

- Live provider execution.
- Live hardware smoke.
- PiKVM input control.
- Redfish mutation.
- Production keychain, daemon, or remote broker integration.
- MCP grant tools.
- Treating conversational chat approval as trusted approval for dangerous
  families.

## Authority Model

```text
approval_required result
-> broker request state
-> trusted operator surface
-> signed broker grant
-> ControlPlane grant verification
-> provider execution only if policy and grant match
```

The signature is truth. Storage is cache.

Grant verification must check:

- signature validity
- signer key identity
- approval request ID
- session ID
- target
- provider
- capability
- parameter fingerprint
- risk family
- expiry
- one-time consumption state
- policy channel constraints
- hard invariant denial

## Signer Model

Production signer options, in preferred order:

1. keychain with user presence
2. separate-UID daemon
3. remote broker

V1 includes a development/test signer abstraction. A local key reachable by the
agent is not production authority and must be documented as such.

## Approval Channels

### Host-Native

Future MCP server work may detect host elicitation support during initialize.
If supported, the host can render a native approval dialog. No tool call may
block indefinitely waiting for a host response.

### Out-Of-Band Push

Default trust anchor. Tool calls return `approval_required` immediately with a
short code, risk summary, `operator_message`, and retry instructions. The
operator approves or denies through a trusted channel. The control plane later
accepts execution only if the signed grant matches the original request
fingerprint.

### Conversational

Conversational approval is forgeable by construction. It is allowed only for
explicitly flagged low-risk families and must be audited as
`conversational_unverified`. It is banned for power, input, boot, media,
provider mutation, credential changes, policy changes, audit changes, and
emergency stop changes.

## MCP Approval Verbs

MCP exposes exactly:

1. request approval
2. deny approval

There is no MCP grant tool. Granting lives only on operator surfaces:

- host-native elicitation dialog
- out-of-band push channel
- watch TUI
- future trusted operator UI

## Timeout Rule

Default maximum blocking time: 20 seconds.

If approval is not completed within the timeout, the tool returns
`approval_required` with:

- short code
- operator message
- human-readable risk summary
- retry instructions

The human can catch up out of band.

## Audit Requirements

Audit must record:

- approval requested
- notifier dispatched or dry-run rendered
- approval denied
- grant signed
- grant verified
- grant rejected
- grant consumed
- provider execution result

Audit records must redact secrets and must not include raw credentials.
