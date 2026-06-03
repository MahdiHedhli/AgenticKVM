# Target Registry

Targets are explicit scope entries. MCP, CLI, API, and workflow inputs cannot
name arbitrary targets and receive execution.

## Rules

- Targets must be explicitly configured.
- Unknown target ids fail closed.
- Duplicate target ids are rejected.
- Every target references a configured provider id.
- Target provider references must exist in the provider registry.
- Disabled targets cannot execute.
- Target metadata must not contain secrets or raw credentials.
- Target allowed modes are enforced when configured.
- A request-supplied provider must match the target's configured provider.

## Metadata

Safe metadata may describe a target with fields such as name, environment,
labels, risk tier, and non-secret operational notes. Metadata must not include
passwords, tokens, private keys, raw credentials, or secret material.

The target registry strengthens, but does not replace, policy target scope.
Policy remains the authority boundary.
