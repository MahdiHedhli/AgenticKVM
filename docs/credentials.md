# Credentials

AgenticKVM does not load real provider credentials in the current scaffold.

## Strategy

Future live providers use credential references, not raw config values.

Allowed future patterns:

- `keychain://agentickvm/lab-pikvm`
- `file://~/.config/agentickvm/secrets/pikvm-lab.ref`
- `env://AGENTICKVM_LAB_PIKVM_CREDENTIAL`
- `vault://agentickvm/lab-redfish`
- `prompt://operator`

The current config loader validates `credential_ref` syntax but does not resolve
the reference. Tests must not read environment secrets.

`credential_ref` values are omitted from provider and target registry summaries.
Audit redaction treats credential reference fields as sensitive.

PiKVM observe placeholder config may include a `credential_ref`, but fixture
mode does not resolve it and live mode remains rejected until manual smoke
gates and a credential backend are approved.

## Disallowed

- raw passwords
- raw tokens
- raw API keys
- committed credential files
- default credentials
- test credentials
- credentials in process argv
- credentials in audit logs
- raw credential references in CLI or MCP output

## Manual Smoke

Environment credential references may be used only in manual live smoke after
operator approval. They are never read by tests and are not a production
credential-store decision.

Screenshot artifacts and audit records must not include credential material,
credential references, cookies, bearer values, or raw screenshot bytes.
