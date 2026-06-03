# Migration From Agentic-KVM

The existing `Agentic-KVM` repository is a donor spike and dogfood prototype. It
is useful for lessons, terminology, experiments, and provider discovery, but it
is not the v2 architecture source.

AgenticKVM is the canonical repository.

## Migration Principles

- Specs define what migrates, not donor code shape.
- Do not copy implementation code during bootstrap.
- Inventory donor behavior before deciding whether it belongs in v2.
- Convert donor behavior into capability, policy, approval, provider, and audit
  requirements.
- Prefer mock and contract tests before real provider code.
- Drop spike behavior that bypasses policy or audit.

## Migration Stages

1. Inventory donor features and risks.
2. Classify each feature by capability family.
3. Identify dangerous actions and required scope.
4. Define contracts and mock behavior.
5. Add control-plane tests.
6. Implement the smallest provider adapter slice.
7. Add opt-in lab validation outside CI.

## Non-Migration List

Do not migrate:

- direct provider calls from tools
- prompt-only safety checks
- implicit target expansion
- raw secret output
- ad hoc audit logs
- provider-owned policy
- real-hardware tests in CI
