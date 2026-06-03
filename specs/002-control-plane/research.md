# Research: Control Plane

## Research Questions

### Where Should Authority Live?

Decision: authority lives in policy evaluated by the control plane.

Reasoning: provider APIs expose operations, not project safety semantics.
Tool descriptions and prompts are not enforceable boundaries. Central policy
gives a single place to reason about scope, mode, limits, approvals, and
invariants.

### Should Providers Know Modes?

Decision: no. Providers should not know visible modes such as Observe,
Assisted, Supervised, or Full Control.

Reasoning: provider-owned policy would fragment behavior, make audit harder,
and let similar capabilities behave differently across providers.

### How Should Unknown Capabilities Behave?

Decision: unknown capabilities return `deny`.

Reasoning: unknown means the project has not specified risk, approval behavior,
provider mapping, audit shape, or limits.

### What Is The Role Of Full Control?

Decision: Full Control reduces prompts for explicitly scoped, allowed actions.
It does not bypass audit, scope, emergency stop, secret handling, limits, or hard
invariants.

Reasoning: Full Control is an operator experience mode, not a root-of-trust
replacement.

### Why Start With Mock Provider?

Decision: mock provider comes before PiKVM or Redfish implementations.

Reasoning: mocks allow policy, approval, audit, schemas, and interface routing
to be verified without real hardware, credentials, or availability risks.

## Alternatives Rejected

### Direct Tool-To-Provider Calls

Rejected because tools cannot reliably enforce target scope, approval state,
audit obligations, dangerous action classification, or provider-specific risk.

### Provider-Specific Policy

Rejected because policy semantics would drift across adapters and provider
behavior would become the practical authority boundary.

### Prompt-Only Safety

Rejected because prompt text is not an enforceable control. Safety must be in
contracts, policy, approvals, scope, audit, and tests.

### Real-Hardware CI

Rejected because CI should be deterministic, safe, and credential-free. Real
hardware testing belongs in explicit lab workflows outside default CI.
