# Provider Registry

Providers are configured execution adapters. They are not authority boundaries
and they do not decide policy, scope, approval, or audit behavior.

## Rules

- Providers must be explicitly registered.
- Unknown provider ids fail closed.
- Duplicate provider ids are rejected.
- Provider type is explicit and validated.
- Config cannot dynamically import provider classes.
- Disabled providers cannot execute.
- `mock` is the only default executable provider type in this lane.
- Real provider types may appear only as disabled placeholders until their
  provider specs, contracts, and safety tests are complete.

## Current Types

- executable: `mock`
- disabled placeholders: `pikvm`, `redfish`, `ilo`, `idrac`, `ipmi`,
  `supermicro`, `proxmox`

External interfaces must resolve providers through the registry before creating
a control-plane request. A provider id supplied by a request is treated as
untrusted input and must match the configured target provider.
