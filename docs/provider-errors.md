# Provider Errors

Provider errors are structured safety signals. They must not leak credentials
or cause an interface to bypass `ControlPlane`.

## Categories

- config
- credential
- network
- provider
- protocol
- safety

## Rules

- Errors normalize into `ProviderActionResult`.
- Public messages are redacted when the error is not safe to show.
- Auth and secret errors must not include raw credentials or secret references.
- Unsafe operation and mutation-blocked errors are never retryable.
- Retryable errors are limited to safe network/provider availability classes.
- Approval can resolve only selected credential-reference problems, never
  unsafe operations or policy violations.

## Taxonomy

The canonical table lives in
`specs/003-real-provider-readiness/contracts/provider-error-taxonomy.md`.

## Interface Behavior

CLI and MCP should surface normalized provider results with:

- `status`
- `provider_id`
- `provider_type`
- `target`
- `capability`
- `error_code`
- `error_message`
- `retryable`
- redacted provider data

Provider errors do not authorize retries, approvals, or target changes by
themselves.

## Current Implementation

The taxonomy is implemented in `src/agentickvm/providers/errors.py` and covered
by unit plus CLI/MCP consistency tests. It is ready for future live providers to
use, but no live provider transport exists yet.
