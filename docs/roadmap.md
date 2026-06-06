# Roadmap

## 0. Bootstrap

- Create canonical repository structure.
- Add constitution, specs, contracts, docs, examples, scaffold, and tests.
- Keep real hardware out of scope.

## 1. Control Plane Core

- Implement policy loader and capability registry.
- Implement default-deny unknown capability resolution.
- Implement approval request creation.
- Implement structured audit event writer.

## 2. Mock Provider

- Expand safe mock provider behavior.
- Add mock fixtures for capability families.
- Add contract tests for provider execution boundaries.
- Add explicit provider registry and target registry.
- Add safe mock-only config loading.
- Add a mock-only CLI adapter over the same control-plane path.
- Add expanded mock observation, input, power, media, boot, BMC, network, and
  storage contract coverage.

## 3. MCP Interface

- Add MCP tools that submit capability requests.
- Resolve MCP targets and providers through explicit registries.
- Prove MCP tools cannot call providers directly.
- Add contract tests for tool-to-control-plane routing.
- Add CLI/MCP consistency matrix for mock-target actions.
- Add dependency-free mock-only MCP SDK adapter scaffold over `MCPRouter`.
- Add dependency-free mock-only MCP host compatibility layer over the SDK
  adapter, including JSON-safe tool listing, schema output, tool calls,
  approval-required pass-through, and structured error serialization.
- Add mock-only MCP host approval lifecycle fixtures for explicit approval
  response submission, one-time/session approval resumption, JSONL audit
  persistence, hash-chain verification, and safe result serialization.
- Add mock-only host provider-error lifecycle fixtures, approval/provider-error
  resumption cases, audit integrity expansion, artifact metadata lifecycle
  checks, golden host result fixtures, and lightweight host result schema
  validation.
- Add production audit-store requirements, checkpoint-backed tail-truncation
  detection, export/import verification, retention policy validation, audit
  failure fail-closed coverage, and host audit conformance fixtures before live
  MCP server dependency selection.
- Add MCP SDK dependency/security review framework, candidate matrix, live MCP
  server boundary ADR, live-server acceptance gate, dependency gate tests, and
  audit-store gate integration before selecting or adding a live SDK/server
  dependency.
- Keep live MCP SDK server and client integration deferred until dependency,
  packaging, host integration, and security questions are settled.

## 4. Real Provider Readiness

- Add readiness gates before any real provider implementation.
- Add disabled placeholder provider contracts.
- Require observe-only first slice.
- Add PiKVM and Redfish observe-only specs, fake transports, fixture-backed
  adapters, disabled config placeholders, CLI/MCP fixture tests, and manual
  smoke docs.
- Add provider conformance suite, normalized provider result envelope, provider
  error taxonomy, transport security policy model, credential reference
  contract, live observe ADR, and MCP SDK adapter research.
- Add PiKVM-specific live observe ADR, fake-only transport boundary, fixture
  contracts, config hardening, and screenshot artifact safety checks before any
  live PiKVM client code.
- Preserve host-level artifact metadata and provider-error conformance before
  exposing real observe providers through any future MCP server.
- Keep CI mock-only.
- Require manual smoke docs and human approval before live testing.
- Maintain provider taxonomy distinguishing out-of-band providers from future
  in-band remote session and browser/session providers.

## 5. PiKVM Provider

- Write PiKVM provider spec.
- Implement the smallest safe observe-only live adapter slice after readiness
  gates pass.
- Add opt-in lab tests outside CI.
- Status: not started; live transport remains blocked on operator approval,
  transport/TLS design review, and manual smoke gates.

## 6. Redfish Provider

- Write Redfish provider spec.
- Implement the smallest safe GET-only observe live adapter slice after
  readiness gates pass.
- Follow the same fake-first transport injection and fixture contract pattern
  proven by PiKVM before adding Redfish live code.
- Add opt-in lab tests outside CI.
- Status: not started; live transport remains blocked on operator approval,
  transport/TLS design review, Redfish live observe ADR, and manual smoke
  gates.

## 7. Operator Approval UX

- Implement explainable prompts.
- Support approval reuse inside exact session scope.
- Add audit and expiration tests.
- Add explicit local approval queue transport with CLI list/show/approve/deny/
  expire commands, one-time consumption, session-scoped reuse, redaction, and
  optional local audit persistence.
- Add local read-only operator console/status output for providers, targets,
  policy mode, pending approvals, audit verification, and live-provider default
  status.

## 8. Hardening And Public Beta

- Add threat-model test cases.
- Add provider conformance suite.
- Add docs for safe deployment.
- Add a GitHub Pages-ready static site for product positioning, safety
  guardrails, provider taxonomy, MCP/agent integration, getting started, and
  roadmap review.
- Add mock-only CI, static GitHub Pages workflow, package metadata checks,
  docs/spec validation, release safety regression tests, contributor workflow
  docs, release readiness docs, and branch review package.
- Run security review before public beta.

## 9. Future In-Band Remote Session Providers

- Document RustDesk, VNC, RDP, and MeshCentral as future in-band remote session
  providers, not out-of-band providers.
- Start with provider inventory and session metadata observe-only specs.
- Keep clipboard, file transfer, remote command execution, agent installation,
  and unattended control disabled by default and gated by policy/approval.
- Status: roadmap-only; no implementation, network transport, credentials, or
  remote desktop behavior exists.

## 10. Future Browser/Session Providers

- Document BrowserBridge and desktop/session brokers as future session-level
  providers.
- Start with session inventory and safe observe metadata only.
- Status: roadmap-only.

## 11. Public Website

- Static site scaffolded under `site/`.
- GitHub Pages setup documented in `docs/github-pages.md`.
- Static GitHub Pages workflow added to publish only `site/` after merge and
  repository Pages settings review.
- Site safety checks assert no trial SDK dependency, no tracking, no live
  provider claims, no overclaim phrases, and no workflow secrets.

## 12. Release Quality Gates

- Mock-only CI workflow added for package checks, docs/spec validation, and
  pytest.
- Static GitHub Pages workflow added with no secrets and no dependency install.
- Package metadata and import validation added through `scripts/check-package.py`.
- Package artifact readiness validation added through `scripts/build-package.py`;
  wheel/sdist build remains deferred unless optional build tooling is present.
- CLI smoke matrix added through `scripts/smoke-cli.py`.
- Lint and type sanity gates added through `scripts/lint-sanity.py` and
  `scripts/type-sanity.py`.
- Static site preview validation added through `scripts/check-site.py`.
- Release manifest generation added through
  `scripts/generate-release-manifest.py`.
- Docs/spec/site validation added through `scripts/validate-docs.py`.
- Release safety regression suite added for provider, target, policy, config,
  workflow, and public-claim invariants.
- Development, testing, packaging, coverage policy, release readiness, release
  checklist, release artifacts, branch review, and PR review docs added.
- Status: branch-ready for human review; live providers, live MCP server, and
  SDK trial dependency remain deferred.

## 13. Next-10 Integration Branch

- Release-quality and GitHub Pages branches are integrated through the
  package-release hardening base.
- Python MCP SDK trial reviewed; decision is continue trial and hold mainline
  adoption until human review.
- Mock-only MCP stdio mainline adoption remains deferred; no `mcp` dependency
  added.
- Local operator approval transport added.
- Live PiKVM observe, live Redfish observe, and PiKVM input-control phases are
  explicitly gated in `docs/live-provider-and-input-gates.md`; no live provider
  or input-control code was added.
- Local operator console added through `agentickvm status` and
  `agentickvm console`.
- SQLite audit backend v1 added with explicit-path runtime opt-in,
  verification, listing, export, and tamper-detection tests.
- Safe recovery playbook framework added with dry-run and mock/fake execution
  through `MCPRouter` and `ControlPlane`.
- Status: integration branch ready for human review; live providers, live MCP
  server, SDK trial dependency, real input control, and live recovery playbooks
  remain deferred.

## 14. Audit Beta Readiness Branch

- SQLite audit backend v1 hardened with checkpoint, inspect, checkpoint-aware
  export, reopen verification, malformed store handling, and tamper/deletion
  tests.
- Audit CLI workflows expanded for list, verify, export, checkpoint, and inspect
  operations.
- Local approval queue hardened with denial, expiry, consumed-event, redaction,
  fingerprint mismatch, hard-invariant, and malformed-store tests.
- Recovery playbook safety hardened with required risk/rollback metadata, known
  tool and capability validation, redacted step output, and policy/approval stop
  behavior.
- Live-provider preflight gates added for future PiKVM/Redfish observe-only
  work. The gates are local, preflight-only, CI/test-mode-blocked, observe-only,
  and do not instantiate providers, resolve credentials, or contact hardware.
- Public beta risk register, readiness checklist, and merge review package
  added.
- CI/release gates now require beta/preflight/audit docs and reject committed
  generated local audit DBs, exports, checkpoints, approval queues, screenshots,
  and artifact files.
- Status: public beta candidate branch ready for final local validation and
  human merge review; live providers, live MCP server, SDK trial dependency,
  real input control, and production external audit backend remain deferred.
