# Public Beta Security Statement

AgenticKVM public beta is a safety-first, mock-first release candidate. It is
intended for review, local mock testing, and provider-readiness planning. It is
not approval for unattended production hardware use.

## Security Posture

The beta preserves these core safety rules:

- policy is the authority boundary
- unknown capabilities fail closed
- tools, CLI paths, MCP adapters, host compatibility layers, and playbooks must
  route through registries and `ControlPlane`
- provider adapters do not own policy
- `approval_required` is a first-class result
- approval grants bind to session, target, provider, capability, fingerprint,
  scope, and expiry
- audit is mandatory
- secrets and credential references are redacted
- real providers are disabled by default
- CI is mock-only

## Audit

The beta includes local JSONL audit support and SQLite audit backend v1. Audit
events are redacted before persistence and hash chained for tamper evidence.
SQLite audit supports explicit-path persistence, list, verify, export,
checkpoint, and inspect workflows.

The SQLite backend is local and explicit-path only. External production audit
backend, SIEM integration, checkpoint signing, and managed retention remain
deferred.

## Credentials

Configuration may contain `credential_ref` values for future provider work.
Tests and current runtime paths do not resolve credential references. Do not
commit raw credentials, tokens, cookies, API keys, private keys, real hostnames,
or real IP addresses.

## Artifacts

Screenshots, screen observations, audit exports, approval queues, generated
manifests, and local audit databases can contain sensitive operational context.
Do not commit generated artifacts. Use `/tmp` or ignored `artifacts/` paths for
local validation output.

## Live Providers

Live PiKVM and Redfish execution are deferred. The preflight gate is a readiness
check only; it does not authorize live smoke or hardware operation. Future live
smoke must be manual, operator-approved, observe-only for the relevant phase,
and backed by audit and approval transport.

## Not For This Beta

Do not use this beta for:

- unattended production hardware recovery
- live PiKVM keyboard, mouse, paste, or hotkey input
- live Redfish reset, boot override, virtual media, BIOS, firmware, storage,
  network, or account changes
- storing or sharing real credentials
- bypassing policy, approval, audit, provider registry, or target registry

## Vulnerability Reporting

Do not open public issues for exploitable vulnerabilities. Follow
[`SECURITY.md`](../SECURITY.md) and report privately to the maintainers with
redacted reproduction steps,
affected commit/version, expected impact, and whether real hardware,
credentials, or audit data were involved.
