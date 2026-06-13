# Approval Notifiers

Approval Broker v1 uses out-of-band approval as the default trust anchor.

The first notifier implementation is local and network-free. It renders the
same Allow/Deny payload shape that a future ntfy, Pushover, or Telegram adapter
can send, but it does not contact external services, require credentials, or
grant approval by itself.

## Local Notifier

`LocalApprovalNotifier` records notification payloads in memory for tests and
local development. Each payload includes:

- approval request ID
- short code
- operator message
- risk summary
- Allow action metadata
- Deny action metadata

The notifier does not sign grants. Signing happens only through a broker signer
used by trusted operator surfaces such as the watch command or future remote
broker.

## Future Network Notifiers

Future notifier adapters may target ntfy, Pushover, or Telegram, but they must:

- be disabled by default
- require explicit endpoint/config
- never read environment secrets in tests
- support fake transports in CI
- include Allow and Deny actions
- route Allow through the broker signer
- never expose an MCP grant tool
- audit dispatch and decision outcomes
