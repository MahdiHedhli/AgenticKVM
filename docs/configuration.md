# Configuration

AgenticKVM configuration is explicit, local, and fail-closed.

## Current Loader

The current loader accepts JSON-compatible YAML documents parsed by Python's
standard `json` module. This avoids adding a YAML dependency before the
configuration threat model and parser requirements are settled.

Examples:

- `examples/config/mock-only.yaml`
- `examples/config/provider-placeholders.yaml`
- `examples/config/pikvm-observe-placeholder.yaml`
- `examples/config/pikvm-observe-fixture.yaml`
- `examples/config/redfish-observe-placeholder.yaml`
- `examples/config/lab-observe-only.example.yaml`

The CLI defaults to a safe built-in mock-only config when no `--config` path is
provided. Tests do not read global user config, environment secrets, or
production credentials.

## Required Shape

Configuration declares:

- explicit providers
- explicit targets
- default policy mode

Provider and target ids are stable strings. Unknown provider types, unknown
target provider references, duplicate ids, disabled providers, disabled targets,
and invalid config shapes fail closed.

## Secrets

Config must not contain secrets. The loader rejects secret-shaped keys such as:

- `password`
- `token`
- `api_key`
- `secret`
- `private_key`
- `credential`
- `bearer`
- `session_cookie`

Config also rejects dynamic import keys such as `class`, `module`, `factory`,
and `import`. Provider classes are not loaded from config.

## Real Providers

Real provider entries remain deferred. They may be represented as disabled
placeholders with no endpoints and no credentials, but they are not executable
by default.

Enabled real provider entries are rejected until future provider-specific gates
explicitly allow them.

PiKVM and Redfish fixture mode is available for offline tests only:

```text
"metadata": {"fixture_mode": true}
```

Fixture mode builds a fake observe-only adapter with no live transport and no
credentials. Placeholder examples keep `fixture_mode` false and `enabled`
false.

For PiKVM, fixture mode must use `transport: "fake"` or the implicit fake
transport default. `fixture_mode` and `live_mode` cannot both be true. Enabled
PiKVM live-provider config is rejected until live smoke gates and a future live
transport implementation exist.

TLS verification defaults to true. Disabling TLS verification without an
explicit override fails closed, and insecure TLS is not a default example
setting.

PiKVM screenshot/artifact and audit paths in examples are placeholders only.
Future live smoke must configure explicit local paths outside the repository.

## Credential References

Provider entries may include a future `credential_ref` value using an approved
scheme such as `keychain://`, `file://`, `env://`, `vault://`, or `prompt://`.
The current loader validates the reference but does not resolve it. Raw
credential fields remain rejected.
