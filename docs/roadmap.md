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

## 8. Hardening And Public Beta

- Add threat-model test cases.
- Add provider conformance suite.
- Add docs for safe deployment.
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
