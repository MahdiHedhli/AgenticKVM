# Implementation Plan: Redfish Observe-Only Provider

## Phase 1: Spec And Contracts

- Define GET-only observe boundary.
- Document forbidden Redfish operations.
- Add manual smoke checklist for future live tests.

## Phase 2: Fake Client Contract

- Add a Redfish client interface that accepts an injected fake transport.
- Provide fixture responses for service root, systems, sensors, event logs, and
  manager status.
- Ensure fake transport rejects non-GET methods.

## Phase 3: Mocked Provider Adapter

- Add a test-enabled Redfish observe-only adapter.
- Keep default real Redfish posture disabled and non-executable.
- Support only observe capabilities through `execute_authorized`.

## Phase 4: Registry And Config

- Add disabled config placeholders with no secrets.
- Allow explicit fixture mode for tests only.
- Preserve fail-closed behavior for enabled real provider config.

## Phase 5: Interface Tests

- Prove MCP and CLI requests resolve registered fake Redfish targets.
- Prove mutating tools deny or fail unsupported without provider mutation.
- Prove audit records provider observe execution.

## Constraints

- No live Redfish network calls.
- No credentials in config or tests.
- No POST, PATCH, DELETE, reset, media, boot, BIOS, firmware, storage, network,
  account, or credential mutations.
- No CI real hardware.
