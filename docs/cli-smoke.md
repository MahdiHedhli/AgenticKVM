# CLI Smoke Matrix

`scripts/smoke-cli.py` runs a safe, mock-only CLI smoke matrix for release
branches and CI.

## Scope

The smoke matrix uses:

- the built-in mock config
- checked-in fixture config for PiKVM observe-only behavior
- local JSON output capture
- no global config lookup
- no credential reference resolution
- no live provider calls
- no network listeners
- no real hardware

## Command

```bash
python scripts/smoke-cli.py
```

The script exits nonzero on failure and prints a concise JSON result suitable
for CI logs.

## Covered Cases

- CLI import through the public package entry point
- list providers
- list targets
- mock observe screen
- mock power state
- PiKVM fixture observe screen
- unknown tool fails closed
- unknown target fails closed
- disabled provider target fails closed
- dangerous mock action returns `approval_required`
- raw secret reveal returns `denied`
- policy modification returns `denied`
- output is JSON-safe
- output does not include obvious secret-like values

## Non-Goals

The smoke matrix does not:

- run live provider smoke tests
- call PiKVM, Redfish, iLO, iDRAC, IPMI, Supermicro BMC, Proxmox, RustDesk,
  VNC, RDP, MeshCentral, or physical hosts
- open network listeners
- read environment secrets
- resolve credential references
- auto-approve gated actions
- validate future live MCP server behavior

## Release Gate

Before a release-quality branch is merged, this command should pass alongside:

```bash
python scripts/check-package.py
python scripts/build-package.py
python scripts/validate-docs.py
uv run --offline --with pytest --python python3.13 python -m pytest
```
