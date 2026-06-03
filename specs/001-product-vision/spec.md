# Specification: Product Vision

## Summary

AgenticKVM is a spec-driven control plane for safe agentic out-of-band
infrastructure operations. It lets agents help operate real machines while
keeping authority in policy, approvals, target scope, provider contracts, and
structured audit.

## Problem

Out-of-band control systems are powerful. They can power-cycle machines, mount
media, change boot order, modify firmware, alter storage, and expose secrets.
Direct agent access to those systems creates unacceptable risk because prompts,
tool descriptions, and provider-specific APIs are not authority boundaries.

## Goals

- Provide a canonical, mass-consumption implementation named AgenticKVM.
- Make policy the authority boundary for all actions.
- Make operator approval explainable and auditable.
- Make dangerous operations explicit, scoped, and gated.
- Support multiple provider adapters without provider-owned policy.
- Use mocks and contracts before real hardware integrations.
- Preserve a strict separation between lessons from the donor spike and the
  canonical v2 architecture.

## Non-Goals

- Migrating implementation code from `Agentic-KVM` during bootstrap.
- Providing real hardware control in the first repository slice.
- Treating Full Control as unrestricted machine authority.
- Letting agents self-escalate policy, credentials, scope, or provider access.
- Using real hardware in CI.

## Users

- Operators who need agent assistance while retaining control and auditability.
- Infrastructure engineers integrating OOB providers such as PiKVM and Redfish.
- Security reviewers validating policy, approval, audit, and provider behavior.
- Agent/tool authors who need a safe, constrained control-plane interface.

## Product Principles

- The operator chooses visible control mode.
- The control plane converts intent into explicit capability requests.
- Policy decides before approval or provider execution.
- Approvals explain material risk, scope, and audit outcome.
- Provider adapters execute authorized requests only.
- Audit is structured and mandatory.
- Unknown capabilities deny by design.

## Visible Control Modes

- Observe: read-only observation. No state-changing provider actions.
- Assisted: conservative mode for guided operation with approval for meaningful
  state changes.
- Supervised: richer operation with dangerous actions gated and explained.
- Full Control: no routine prompts for in-scope allowed work, but all hard
  invariants remain active.
- Custom: explicit policy for a specific environment, target class, or session.

## Required Outcomes

- A new repository identity: `AgenticKVM`, package `agentickvm`, CLI
  `agentickvm`.
- A constitution that is treated as the highest authority.
- Product and control-plane specs with plans, tasks, and contracts.
- Security, architecture, provider, approval, migration, roadmap, heartbeat, and
  threat-model docs.
- Example policies for all visible modes.
- Minimal Python scaffolding with a base provider contract and safe mock.
- Initial tests proving importability, safety defaults, and contract presence.

## Success Criteria

- A new contributor can understand the authority boundary from the README and
  constitution.
- Dangerous actions and Full Control invariants are documented before real
  provider work begins.
- The test suite runs without real hardware.
- Contract schemas exist for policy, capability registry, approval request, and
  audit event.
- The donor spike is explicitly documented as non-authoritative.
