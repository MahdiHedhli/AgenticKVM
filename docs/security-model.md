# Security Model

AgenticKVM assumes agent requests can be mistaken, overbroad, prompt-injected,
or inconsistent with operator intent. Safety is enforced through policy,
approval, scope, provider contracts, audit, and tests.

## Trust Boundaries

- Agent text is untrusted intent.
- MCP, CLI, API, and workflow inputs are untrusted until converted into
  capability requests.
- Policy is the authority boundary.
- Providers are execution adapters, not trust anchors.
- Provider and target registries are validation gates, not permission grants.
- Audit is mandatory evidence.

## Default-Deny Behavior

Unknown capabilities, malformed requests, missing registry entries, missing
policy entries, ambiguous provider mappings, and missing scope deny by default.

Unknown providers, unknown targets, disabled providers, disabled targets,
unknown provider types, and provider/target mismatches fail closed before
provider execution.

## Secrets

Secrets are represented by references and redacted values. Raw secret reveal is
not a default behavior in any mode, including Full Control.

Configuration must not contain raw credentials or secret-shaped keys. The
current loader rejects keys such as `password`, `token`, `api_key`, `secret`,
`private_key`, and `credential`.

## Scope

Target and session scope must be explicit for dangerous or destructive actions.
Agents cannot silently widen target scope, add credentials, or move to another
target outside the active session scope.

Targets must be explicitly configured. Request-supplied target ids and provider
ids are untrusted until validated against the registries.

## CI

CI must not use real hardware, real credentials, real BMCs, real KVM devices, or
production network endpoints. Tests should use mocks, fixtures, schemas, and
offline contract checks.

## Emergency Stop

Emergency stop must not be disableable by an agent-controlled request. Future
implementations must treat emergency stop as a hard invariant, not a policy
preference.

## Audit

Audit events must exist for denied, allowed, approval-requested, approved,
failed, and executed requests. An agent cannot disable audit or erase audit
artifacts.
