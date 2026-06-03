# Security Policy

AgenticKVM exists to make agentic out-of-band operations safer. Security
requirements are product requirements, not optional hardening work.

## Reporting Vulnerabilities

Do not open public issues for exploitable vulnerabilities. Report privately to
the project maintainers with:

- affected version or commit
- reproduction steps
- observed impact
- whether real hardware, credentials, or audit data were involved

Maintainers should acknowledge receipt, triage severity, and coordinate a fix
before public disclosure.

## Safety Baseline

The following rules apply to all implementations:

- Policy is the authority boundary.
- Unknown capabilities default to deny.
- Tools cannot call providers directly.
- Provider adapters do not own policy.
- Full Control bypasses prompts, not scope, audit, or invariants.
- Agents cannot self-escalate.
- Secrets are never revealed by default.
- Audit is mandatory.
- Real hardware is never used in CI.

## Hard Invariants

These apply even in Full Control:

1. Agent cannot change its own policy.
2. Agent cannot disable audit logging.
3. Agent cannot disable emergency stop.
4. Agent cannot silently expand target scope.
5. Agent cannot silently add credentials.
6. Agent cannot reveal raw secrets by default.
7. Agent cannot persist new background services without logging them.
8. Agent cannot move to another target unless it is inside session scope.
9. Agent cannot erase audit artifacts.
10. Agent cannot hide material risk from the operator.
11. Agent cannot run destructive OOB actions against real hardware unless target
    and session scope explicitly allow it.
12. Agent cannot treat provider-specific reset, boot, firmware, or storage
    actions as generic low-risk actions.

## CI And Real Hardware

CI must not contact real BMCs, KVM devices, Redfish endpoints, PiKVM devices,
network power controllers, or production infrastructure. Tests must use mock
providers, fixtures, schemas, and offline contract checks.

## Secrets

Secrets are redacted by default. Raw secret reveal requires an explicit
capability, explicit scope, explainable operator approval, audit logging, and a
non-default policy path. Logs and audit events must record secret references or
redacted values, not raw secret material.

## Unsafe Requests

Requests that weaken safety gates, erase audit artifacts, bypass policy, or hide
material operator risk are not valid AgenticKVM behavior.
