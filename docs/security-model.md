# Security Model

AgenticKVM assumes agent requests can be mistaken, overbroad, prompt-injected,
or inconsistent with operator intent. Safety is enforced through policy,
approval, scope, provider contracts, audit, and tests.

## Trust Boundaries

- Agent text is untrusted intent.
- MCP, CLI, API, and workflow inputs are untrusted until converted into
  capability requests.
- The mock-only MCP SDK adapter is untrusted interface input translated into
  `MCPToolRequest`; it is not an authority boundary.
- The mock-only MCP host compatibility layer is untrusted host-style input
  translated through `MCPSDKAdapter`; it is local only and is not a live server
  or authority boundary.
- Policy is the authority boundary.
- Providers are execution adapters, not trust anchors.
- Provider and target registries are validation gates, not permission grants.
- Audit is mandatory evidence.

Provider categories have different trust and availability assumptions.
Out-of-band providers can operate below or outside the OS. Future in-band
remote session providers such as RustDesk, VNC, RDP, and MeshCentral generally
depend on a running OS, reachable network path, remote access service, and
credentials or user/session state.

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
`private_key`, `credential`, `bearer`, and `session_cookie`.

The only credential-shaped config key currently allowed is `credential_ref`.
It validates future reference syntax and is not resolved by tests or the
current runtime.

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

PiKVM and Redfish provider-specific tests use fake transports only. The fake
Redfish transport rejects non-GET methods. The provider modules do not define a
live transport implementation, and placeholder configs remain disabled by
default.

PiKVM now has a provider-specific fake observe transport boundary and synthetic
fixture contracts. The live PiKVM transport is still absent. Fixture mode must
be explicit and cannot be combined with live mode.

Transport security policy defaults to TLS verification enabled, no redirects,
GET-only Redfish first slice, observe-only PiKVM first slice, bounded response
size, and no retry for unsafe or mutating capabilities.

The MCP SDK adapter scaffold and host compatibility layer do not open a server,
listen on a port, import a live SDK, resolve credentials, or contact live
providers. They use mock config by default and fixture config only when
explicitly supplied.

Host compatibility schemas and results are JSON-safe and secret-redacted.
`approval_required` is preserved as a first-class result and is never
auto-approved by the host layer.

## Emergency Stop

Emergency stop must not be disableable by an agent-controlled request. Future
implementations must treat emergency stop as a hard invariant, not a policy
preference.

## Audit

Audit events must exist for denied, allowed, approval-requested, approved,
failed, and executed requests. An agent cannot disable audit or erase audit
artifacts.

The local JSONL audit scaffold writes only to an explicitly configured file
path. Test coverage uses temporary directories only. JSONL records are redacted
before write and include a simple previous-hash/event-hash chain for
tamper-evidence.

Provider errors and provider results normalize into structured envelopes before
CLI/MCP output. Secret-shaped fields and credential references are redacted.

Screenshot and screen observations are sensitive. The current scaffold records
metadata only, rejects repo-default artifact paths, redacts raw byte fields in
audit, and ignores common local screenshot artifact paths.

Remote desktop streams, screenshots, clipboard contents, file transfer,
remote command execution, remote access agent changes, and unattended control
are high-risk in-band provider behaviors. They are roadmap-only and must require
explicit capability mapping, policy gates, approval behavior, redaction, and
audit before implementation.
