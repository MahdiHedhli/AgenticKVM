# Transport Security Policy

Future live observe transports must satisfy this policy before implementation.

## Defaults

- TLS verification: enabled
- Insecure TLS: disabled
- Redfish first-slice methods: GET only
- PiKVM first-slice behavior: observe-only
- Redirects: disabled unless a provider spec allows them
- Tests: fake transports only
- Secrets: never read from environment during tests

## Timeouts

- connect timeout must be positive
- read timeout must be positive
- total timeout must be positive
- total timeout must not be less than connect timeout

## Response Policy

- Response size must have a maximum.
- Response content type must be validated when applicable.
- Unknown response shapes fail closed.

## Retry Policy

- Retry only observe capabilities.
- Retry only retryable timeout, connection, or rate-limit errors.
- Never retry unsafe or mutating capabilities.
- Never retry TLS verification, auth, protocol validation, unsafe operation, or
  mutation-blocked errors.

## Audit

Audit must include redacted transport policy summary, provider, target,
capability, method, timeout policy, TLS verification policy, and structured
error or result.
