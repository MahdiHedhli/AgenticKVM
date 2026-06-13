# Approval Channel Policy

## Host-Native

Host-native approval may be used only when host elicitation support is detected
at MCP initialize time. If the host does not answer before the configured
timeout, the tool returns `approval_required` and falls back to out-of-band
operator flow.

## Out-Of-Band

Out-of-band approval is the default trust anchor. The operator approves or
denies through a trusted surface outside the agent chat. The broker signs any
grant produced by that surface.

Allowed operator surfaces:

- push notifier with Allow/Deny
- watch TUI
- future trusted operator UI
- future remote broker

## Conversational

Conversational approval is untrusted by default. It is allowed only for
explicitly flagged low-risk families and must be audited with
`conversational_unverified`.

Conversational approval is banned for:

- power
- input
- boot
- media
- provider mutation
- credential changes
- policy changes
- audit changes
- emergency stop changes

Conversational approval cannot bypass signed grant verification.
