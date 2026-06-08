# Changelog

All notable changes to AgenticKVM will be documented in this file.

## Unreleased - Public Beta Cutover Candidate

Proposed pre-release tag: `v0.1.0-public-beta.1`.

Package metadata remains `0.0.0` until a maintainer explicitly approves a
version bump.

### Added

- Static GitHub Pages-ready site and safe Pages workflow.
- Mock-only CI and release-quality validation scripts.
- Package metadata, CLI smoke, lint sanity, type sanity, docs/spec validation,
  site validation, and release manifest checks.
- Local operator approval queue transport with CLI list/show/approve/deny/
  expire flows.
- Local operator console/status output.
- SQLite audit backend v1 with explicit-path persistence, hash-chain
  verification, event listing, export, checkpoint, inspect, and tamper tests.
- Safe recovery playbook framework with dry-run, mock execution, audit, and
  ControlPlane routing.
- Live-provider preflight gate framework for future PiKVM/Redfish observe-only
  work.
- Public beta risk register, readiness checklist, merge review package,
  cutover plan, and release notes.
- Final public beta branch review, safety verification, human merge command
  plan, GitHub Pages enablement runbook, tagging plan, and maintainer handoff
  docs.

### Security

- CI remains mock-only and secret-free.
- Unknown providers, targets, capabilities, disabled providers, and disabled
  targets fail closed.
- Live providers, live MCP server behavior, PiKVM input, Redfish mutation, and
  remote desktop providers remain deferred.
- Python MCP SDK dependency trial remains isolated on
  `trial/mock-only-mcp-python-sdk` and is not in mainline metadata.

### Known Limitations

- Wheel/sdist build is deferred unless optional build tooling is available.
- Full lint/type/coverage enforcement remains documented but deferred.
- GitHub Pages repository settings require human enablement after merge.
- The public beta tag and GitHub pre-release are not created by this branch and
  require explicit maintainer approval.
- External production audit backend and SIEM integration are not implemented.
- No production hardware use is supported by this beta candidate.

## 0.0.0 - Bootstrap

- Created canonical AgenticKVM repository foundation.
- Added constitution, product vision, control-plane specification, contracts,
  security model, migration plan, roadmap, and heartbeat prompt.
- Added minimal Python package scaffold with abstract provider contract and safe
  mock provider.
- Added initial unit, contract, and security tests.
