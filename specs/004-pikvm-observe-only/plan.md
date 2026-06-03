# Implementation Plan: PiKVM Observe-Only Provider

## Phase 1: Spec And Contracts

- Define allowed observe-only capabilities.
- Document disallowed mutating actions.
- Add manual smoke checklist for future live tests.

## Phase 2: Fake Client Contract

- Add a PiKVM client interface that accepts an injected fake transport.
- Provide fixture responses for screen/status, power state, and boot status.
- Ensure no default live network transport exists in tests.

## Phase 3: Mocked Provider Adapter

- Add a test-enabled PiKVM observe-only adapter.
- Keep default real PiKVM posture disabled and non-executable.
- Support only observe capabilities through `execute_authorized`.

## Phase 4: Registry And Config

- Add disabled config placeholders with no secrets.
- Allow explicit fixture mode for tests only.
- Preserve fail-closed behavior for enabled real provider config.

## Phase 5: Interface Tests

- Prove MCP and CLI requests resolve registered fake targets.
- Prove mutating tools deny or fail unsupported without provider mutation.
- Prove audit records provider observe execution.

## Constraints

- No live PiKVM network calls.
- No credentials in config or tests.
- No keyboard, mouse, power, media, boot, storage, network, or BMC mutations.
- No CI real hardware.
