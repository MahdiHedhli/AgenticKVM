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

## 3. MCP Interface

- Add MCP tools that submit capability requests.
- Prove MCP tools cannot call providers directly.
- Add contract tests for tool-to-control-plane routing.

## 4. PiKVM Provider

- Write PiKVM provider spec.
- Implement the smallest safe observe-only adapter slice.
- Add opt-in lab tests outside CI.

## 5. Redfish Provider

- Write Redfish provider spec.
- Implement observe and narrowly scoped power actions.
- Add opt-in lab tests outside CI.

## 6. Operator Approval UX

- Implement explainable prompts.
- Support approval reuse inside exact session scope.
- Add audit and expiration tests.

## 7. Hardening And Public Beta

- Add threat-model test cases.
- Add provider conformance suite.
- Add docs for safe deployment.
- Run security review before public beta.
