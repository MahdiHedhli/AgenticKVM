# Implementation Plan: Control Plane

## Phase 1: Contracts And Constants

- Define policy, capability registry, approval request, and audit event schemas.
- Define required modes, decisions, capability families, dangerous actions, and
  invariants as documented constants.
- Add tests proving contract presence and default-deny design.

## Phase 2: Policy Engine

- Load policy documents.
- Validate policy against schema.
- Resolve capability ids from the registry.
- Return `deny` for unknown or malformed capability requests.
- Apply mode defaults, explicit rules, target scope, session scope, limits, and
  dangerous action gates.

## Phase 3: Approval Broker

- Produce explainable approval requests.
- Support `ask_each_time` and `ask_once_per_session`.
- Store session approvals with exact capability, target, and limit scope.
- Expire approvals deterministically.

## Phase 4: Audit Writer

- Emit structured events for all request states.
- Redact secrets by default.
- Make audit disabling impossible through agent-controlled paths.
- Add tests for denied, approved, failed, and executed requests.

## Phase 5: Provider Adapter Interface

- Finalize base provider interface.
- Keep provider adapters policy-free.
- Add mock provider behaviors for safe local and CI testing.
- Add provider contract tests before real providers.

## Phase 6: Interfaces

- Add MCP and CLI entry points.
- Ensure all interface commands create capability requests and never call
  providers directly.

## Constraints

- No real hardware in CI.
- No direct provider calls from tool, CLI, API, or workflow code.
- No silent scope expansion.
- No raw secret reveal by default.
