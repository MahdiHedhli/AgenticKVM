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

Fixture-backed PiKVM and Redfish observe adapters now exist for offline
contract tests. They are not live providers: they require injected fake
transports, declare `is_real_hardware=false`, return
`performed_on_hardware=false`, and support observe capabilities only.

Provider conformance tests now cover metadata, disabled behavior, unsupported
capabilities, observe-only restrictions, fake transport use, redaction, and
interface-level provider bypass prevention.

## Readiness Gates

Real provider readiness is specified in
`specs/003-real-provider-readiness/`. The first real-provider slice is limited
to observe-only capabilities and still requires manual smoke docs, mock-only CI,
secret-safe config, audit behavior, timeout behavior, and human approval before
live testing.

Provider result normalization, provider error taxonomy, transport security
policy, credential reference policy, live observe ADR, and MCP SDK adapter
research are now part of the readiness surface. They do not implement live
transport.

## Redfish Live Observe Parity Path

Redfish live observe transport should follow the same fake-first pattern being
defined for PiKVM:

- provider-specific ADR before live code
- injected fake transport first
- fixture contracts for expected responses and errors
- disabled live transport by default
- explicit local config outside the repo
- credential references only
- audit and redaction before interface output
- no CI live network access

The first Redfish live slice remains GET-only. `POST`, `PATCH`, `DELETE`,
action URIs such as `ComputerSystem.Reset`, virtual media insert/eject, boot
override, BIOS changes, firmware updates, storage actions, account changes,
network changes, and secret reveal remain out of scope.

Redfish live implementation is deferred until the PiKVM observe boundary is
proven with fake transport contracts and an operator-reviewed manual smoke
plan.

## Provider-Specific Risk

Reset, boot, firmware, storage, power, BMC, and credential operations can vary
widely by provider. They must be represented as explicit capabilities and cannot
be downgraded to generic low-risk operations.

## Provider Readiness Matrix

| Provider | Current status | Allowed observe capabilities | Mutating actions status | Config status | Test status | Live smoke status | CI status | Next gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mock | Default executable safe provider | All current mock observations plus fake state families | Fake only and policy-gated | Built-in and example config enabled | Unit, contract, security | Not applicable | Mock-only | Continue provider conformance tests |
| PiKVM | Offline observe fixture adapter plus disabled placeholder | `observe.status`, `observe.screen`, `observe.screenshot`, `observe.power_state`, `observe.hardware_inventory`, `observe.event_logs`, `observe.boot_status` | Unsupported, denied by policy, or provider-error without hardware action | Disabled placeholder examples; explicit fixture mode for tests | Fake transport, contract, CLI/MCP tests | Deferred, manual only | Fixtures only | Live transport spec and operator-approved smoke |
| Redfish | Offline observe fixture adapter plus disabled placeholder; live transport deferred behind PiKVM parity path | `observe.status`, `observe.power_state`, `observe.hardware_inventory`, `observe.sensors`, `observe.event_logs`, `observe.boot_status` | Unsupported, denied by policy, or provider-error without hardware action; fake transport rejects non-GET | Disabled placeholder examples; explicit fixture mode for tests | Fake GET transport, contract, CLI/MCP tests | Deferred, manual only | Fixtures only | Redfish live observe ADR after PiKVM boundary is proven |
| iLO placeholder | Disabled placeholder | Future observe-only subset | Unimplemented and non-executable | Placeholder only | Placeholder safety tests | Not started | Disabled | Provider-specific observe spec |
| iDRAC placeholder | Disabled placeholder | Future observe-only subset | Unimplemented and non-executable | Placeholder only | Placeholder safety tests | Not started | Disabled | Provider-specific observe spec |
| Supermicro/IPMI placeholder | Disabled placeholder | Future observe-only subset | Unimplemented and non-executable | Placeholder only | Placeholder safety tests | Not started | Disabled | Provider-specific observe spec |
