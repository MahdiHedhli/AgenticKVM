# Credential Reference Policy

AgenticKVM must not store raw provider credentials in repo config, examples,
tests, audit logs, CLI output, MCP output, or provider results.

## Allowed Future Reference Patterns

- `keychain://agentickvm/lab-pikvm`
- `file://~/.config/agentickvm/secrets/pikvm-lab.ref`
- `env://AGENTICKVM_LAB_PIKVM_CREDENTIAL`
- `vault://agentickvm/lab-redfish`
- `prompt://operator`

Environment references are allowed for manual live smoke only and must never be
resolved during tests.

## Disallowed

- raw password in config
- raw token in config
- raw API key in config
- committed credential files
- test credentials
- default credentials
- printing credentials
- passing credentials in process argv
- writing credentials to audit logs
- resolving environment secrets during tests

## Runtime Rule

`credential_ref` values are parsed and validated only. They are not resolved by
the current config loader and must be redacted in outputs.
