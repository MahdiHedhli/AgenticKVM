# MCP SDK Adapter

No live MCP SDK server is implemented yet.

## Future Boundary

The SDK adapter will be a translator:

```text
SDK tool call -> MCPToolRequest -> MCPRouter -> registries -> ControlPlane -> result
```

It must not:

- call providers directly
- instantiate live providers
- read credentials
- change policy
- auto-approve gated actions
- bypass target or provider registries

## Mock-Only First

The first adapter scaffold should use mock-only config by default. Real provider
targets remain disabled unless future readiness gates pass.

## Result Contract

Return the existing MCP result dictionary:

- `ok`
- `denied`
- `approval_required`
- `validation_error`
- `provider_error`
- `policy_error`

Approval-required is not a failure and not an implicit approval.

## Open Decision

The MCP SDK dependency is unresolved. Do not add it until packaging, Python
version support, testability, and security impact are reviewed.
