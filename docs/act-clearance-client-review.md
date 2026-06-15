# ACT Clearance Client Boundary Review

Branch: `feature/act-clearance-client-boundary`

Starting base: `feature/approval-broker-v1`

## Summary

This branch pivots AgenticKVM away from standalone production signed-grant
authority and toward Agentic Control Tower clearance.

AgenticKVM is now framed as a client aircraft of ACT:

- ACT grants or denies clearance.
- AgenticKVM flies the plane.
- ACT owns clearance contract, signing, mobile approval, replay defense,
  one-time clearance consumption, operator channel, and clearance audit.
- AgenticKVM owns capability resolution, local policy, provider and target
  registries, provider execution, local audit, fail-closed behavior, and
  recovery workflows.

## Implemented

- ACT clearance client docs.
- Spec 011 for AgenticKVM as a client of ACT.
- Clearance request/response models labeled as client-side mirrors of ACT's
  future canonical contract.
- ACT client interface and mock ACT client for tests.
- Fail-closed verification seam with ACT-pending proof format placeholder.
- ControlPlane path that calls ACT when local policy requires clearance.
- MCP surface changed to `request_clearance` and `deny_clearance`.
- `clearance_required` MCP result contract with short code, risk summary,
  operator message, retry guidance, and redacted params preview.
- Donor PiKVM port targets for cert pinning, HID redaction, and mouse
  calibration.
- Roadmap, site, release-prep docs, and conformance matrix reset around the
  ACT-cleared killer demo.
- Validation gates for ACT source-of-truth language, no MCP grant tools, parked
  in-band scope, donor port targets, and deferred public beta.

## Important Boundaries

- AgenticKVM does not author the ACT clearance wire contract.
- AgenticKVM does not invent the ACT proof/signature format.
- Default proof verification fails closed outside explicit mock/test mode.
- MCP has no grant, approve, clear, sign, or trust-signer tool.
- Local signed-grant code is retained only as dev/test scaffold and regression
  coverage from the previous branch, not production clearance authority.
- No live providers were implemented or run.
- No hardware, credentials, secrets, or SDK trial dependency were touched.

## Validation

- `python3 scripts/check-package.py`: passed
- `python3 scripts/build-package.py`: passed with documented deferred build
  status
- `python3 scripts/smoke-cli.py`: passed
- `python3 scripts/lint-sanity.py`: passed
- `python3 scripts/type-sanity.py`: passed
- `python3 scripts/validate-docs.py`: passed
- `python3 scripts/check-site.py`: passed
- `python3 scripts/check-public-beta.py`: passed
- `uv run --offline --with pytest --python python3.13 python -m pytest`:
  633 passed

## Deferred

- Alignment with ACT's canonical clearance contract after ACT publishes it.
- Real ACT transport.
- Real ACT proof verification.
- Official Python MCP SDK stdio server.
- Live PiKVM/Redfish execution.
- ACT-cleared killer demo.
