# Provider Contracts

Provider adapters are intentionally narrow. They execute authorized
provider-neutral requests and return structured provider-neutral results.

## Provider Must Declare

- provider id
- provider kind
- version
- supported capabilities
- whether it can touch real hardware
- enabled state
- risk class
- local status behavior
- dry-run validation behavior

Provider declarations enter through the provider registry. Config cannot name an
arbitrary class, module, factory, or import path to create a provider.

## Provider Must Not Decide

- visible mode
- whether a capability is allowed
- whether approval is required
- target scope
- session scope
- secret reveal policy
- audit requirements

## Safe Failure

Providers should fail closed when:

- request shape is invalid
- capability is unsupported
- target mapping is missing
- required parameter is absent
- credentials are missing
- provider-specific operation cannot be mapped safely

The provider registry fails closed before adapter execution when a provider is
unknown, duplicated, disabled, unsupported, or represented only as a disabled
real-provider placeholder.

## Mock First

Every real provider should be preceded by mock behavior and contract tests. The
mock provider must not make network, device, or hardware calls.

The mock provider is currently the only default executable provider. PiKVM,
Redfish, and other real providers remain disabled placeholders until their
readiness gates are met.

Disabled real-provider placeholders may declare future observe-only
capabilities for contract tests, but they cannot execute and must not make
network calls.

## Readiness Gates

Real provider readiness is specified in
`specs/003-real-provider-readiness/`. The first real-provider slice is limited
to observe-only capabilities and still requires manual smoke docs, mock-only CI,
secret-safe config, audit behavior, timeout behavior, and human approval before
live testing.

## Provider-Specific Risk

Reset, boot, firmware, storage, power, BMC, and credential operations can vary
widely by provider. They must be represented as explicit capabilities and cannot
be downgraded to generic low-risk operations.
