# Testing Guide

AgenticKVM tests are mock-only, fixture-only, and safety-first. Tests must not
touch real hardware, live provider networks, credentials, production audit
stores, remote desktop software, or long-running MCP hosts.

## Primary Test Command

Preferred local command:

```bash
uv run --offline --with pytest --python python3.13 python -m pytest
```

If the offline cache is not available, use the safest existing test command and
record the fallback in the handoff.

## Direct Validation Scripts

Release-quality branches also include lightweight validation scripts:

```bash
python scripts/check-package.py
python scripts/validate-docs.py
```

`scripts/check-package.py` validates package metadata, importability, CLI
entry-point metadata, and absence of the trial-only MCP SDK dependency.

`scripts/validate-docs.py` validates required docs/spec/site files, key safety
language, local markdown links, and forbidden public overclaims.

## Test Categories

- `tests/unit/`: focused behavior for small modules.
- `tests/contract/`: cross-module contracts and interface expectations.
- `tests/security/`: fail-closed behavior, redaction, workflow safety, and
  release regression checks.

## Mock-Only Requirements

Tests must not:

- call PiKVM, Redfish, iLO, iDRAC, IPMI, Supermicro BMC, Proxmox, RustDesk,
  VNC, RDP, MeshCentral, or physical hosts
- open network listeners
- read credentials or environment secrets
- resolve credential references
- enable real providers by default
- execute mutating real-provider behavior
- write audit logs or artifacts outside explicit temp paths

## Safety Regression Expectations

Before release or merge, the suite should prove:

- unknown capabilities fail closed
- unknown providers fail closed
- unknown targets fail closed
- disabled providers and targets fail closed
- hard invariants remain denied
- raw secret reveal is denied by default
- audit disabling is denied
- emergency stop disabling is denied
- real provider placeholders remain disabled
- live provider configs are rejected by default
- CLI, MCP, SDK adapter, and host layers cannot bypass `ControlPlane`
- workflows do not require secrets or live provider targets
- public site/docs do not overclaim live provider support

## CI Expectations

GitHub Actions CI is mock-only. It may install Python dependencies for the test
environment, but AgenticKVM tests must not make live provider network calls.

CI should run:

- package metadata checks
- docs/spec validation
- pytest

CI must not run live smoke tests, provider smoke tests, real hardware checks, or
the SDK trial dependency path.

## Adding Tests For Providers

Provider tests should start with mocks, fixtures, or fake transports. Future live
provider smoke tests must be manual, opt-in, operator-approved, and excluded
from CI.

When adding provider coverage, include:

- supported observe behavior
- unsupported capability behavior
- mutation-blocked behavior where relevant
- provider error normalization
- audit emission
- redaction
- no-network guards when practical

## Audit And Artifact Tests

Audit and artifact tests must use temp directories. Audit assertions should
verify redaction and should not store raw screenshots or secret-like values.

Screenshot and screen artifacts are sensitive even when synthetic.
