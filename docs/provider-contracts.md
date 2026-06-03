# Provider Contracts

Provider adapters are intentionally narrow. They execute authorized
provider-neutral requests and return structured provider-neutral results.

## Provider Must Declare

- provider id
- provider kind
- version
- supported capabilities
- whether it can touch real hardware

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

## Mock First

Every real provider should be preceded by mock behavior and contract tests. The
mock provider must not make network, device, or hardware calls.

## Provider-Specific Risk

Reset, boot, firmware, storage, power, BMC, and credential operations can vary
widely by provider. They must be represented as explicit capabilities and cannot
be downgraded to generic low-risk operations.
