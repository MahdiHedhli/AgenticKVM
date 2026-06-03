# PiKVM Observe Fixture Contract

## Purpose

This contract defines the synthetic PiKVM observe fixtures used by AgenticKVM
tests. Fixtures are not live PiKVM output, must contain no secrets, and must
not contain real hostnames, real IP addresses, credentials, cookies, tokens, or
raw screenshots.

## Scope

Fixtures cover the fake-only transport boundary for future PiKVM observe
transport work. They are used in unit, contract, security, CLI, and MCP tests.
They do not authorize live network behavior.

## Fixture Files

- `health.json`: provider health/status fixture.
- `screen-state.json`: synthetic screen observation metadata.
- `power-state.json`: safe power-state observation.
- `screenshot-metadata.json`: metadata-only screenshot artifact contract.
- `error-auth-required.json`: authentication-required error shape.
- `error-timeout.json`: timeout error shape.
- `error-unexpected-shape.json`: malformed response shape.

## Required Fields

### Health

- `health`: string status such as `ok`
- `fixture`: `true`
- `transport`: `fake`

### Screen State

- `kind`: screen observation kind
- `sensitive`: boolean sensitivity flag
- `source`: `synthetic-fixture`

### Screenshot Metadata

- `artifact.kind`
- `artifact.content_type`
- `artifact.byte_length`
- `artifact.storage`
- `sensitive`
- `raw_bytes_included`: must be `false`

### Power State

- `power_state`

## Error Mapping

- `error.code = auth_required` maps to
  `provider_authentication_required`.
- `error.code = timeout` maps to `provider_timeout`.
- Missing required fields map to `provider_response_validation`.
- Unknown fixture routes map to `provider_response_validation`.

## Redaction Requirements

The fake transport must redact or avoid:

- credential references in output
- target-sensitive names
- hostnames
- IP addresses
- URLs
- cookies
- bearer values
- token-like values
- raw screenshot bytes

Audit and external interface output may include screenshot metadata, but never
raw image bytes.

## Safety Requirements

- Fixtures are committed only when synthetic and documentation-safe.
- Fixtures must not be copied from a real PiKVM device.
- Tests must use fake transports only.
- CI must not contact a PiKVM endpoint.
- Mutating methods remain unavailable or fail closed.

## Future Live Comparison

Future live PiKVM implementation may use these fixtures as shape examples, but
live endpoint behavior must still be specified, mocked, and reviewed before
network code is introduced.
