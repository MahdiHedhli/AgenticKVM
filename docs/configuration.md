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
