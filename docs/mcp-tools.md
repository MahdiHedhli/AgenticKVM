# MCP Tools

AgenticKVM's MCP interface is currently an internal scaffold. It defines
MCP-style request and response models, a tool-to-capability registry, and a
router that resolves configured targets/providers and delegates every request
to `ControlPlane`.

No live MCP SDK server is implemented yet. A dependency-free mock-only
`agentickvm.mcp_sdk` adapter scaffold exists and delegates to this same router.
A dependency-free mock-only host compatibility layer exists for local
host-style testing. It wraps the SDK adapter and is not a live MCP server.

## Authority Boundary

MCP tools are not authority boundaries. They do not decide whether an action is
safe, scoped, approved, or allowed.

Every MCP action must flow through:

1. MCP tool request
2. target registry validation
3. provider registry validation
4. capability request
5. ControlPlane
6. policy decision
7. approval if required
8. provider adapter only if allowed
9. audit event
10. structured MCP result

The bad pattern is:

```text
MCP tool -> provider
```

The required pattern is:

```text
MCP tool -> registries -> capability request -> ControlPlane -> policy/approval/audit -> provider
```

For host-style calls, the required pattern is:

```text
host compatibility -> MCPSDKAdapter -> MCPRouter -> registries -> ControlPlane -> policy/approval/audit -> provider
```

## Tool Registry

The MCP registry maps stable tool names to existing capability ids. Unknown tool
names fail closed. Tool mappings to unknown capabilities fail closed.

Initial mappings include:

| Tool | Capability |
| --- | --- |
| `observe_screen` | `observe.screenshot` |
| `get_status` | `observe.status` |
| `get_power_state` | `observe.power_state` |
| `get_hardware_inventory` | `observe.hardware_inventory` |
| `get_sensors` | `observe.sensors` |
| `get_event_logs` | `observe.event_logs` |
| `get_boot_status` | `observe.boot_status` |
| `power_on` | `power.on` |
| `graceful_restart` | `power.graceful_restart` |
| `force_restart` | `power.force_restart` |
| `mount_media` | `media.mount_approved_iso` |
| `change_boot_order` | `boot.override` |
| `type_text` | `input.keyboard_type` |
| `modify_policy` | `session.modify_policy` |
| `reveal_secret` | `secrets.raw_reveal` |

## Result Statuses

MCP router results use explicit statuses:

- `ok`
- `denied`
- `approval_required`
- `validation_error`
- `provider_error`
- `policy_error`

Approval-required is a first-class result, not a failure and not an implicit
approval.

## Safety Rules

- Unknown MCP tools fail closed.
- Unknown capability mappings fail closed.
- Unknown targets fail closed.
- Unknown providers fail closed.
- Request provider values must match the target's configured provider.
- Disabled providers and disabled targets fail closed.
- Requested mode in an MCP request cannot self-escalate the active policy.
- Raw secret reveal is denied by default.
- Denied and approval-required requests do not reach the provider.
- Returned params and provider results are redacted before MCP output.
- The current scaffold supports the mock provider plus explicit fixture-mode
  PiKVM/Redfish observe providers for offline tests only.
- PiKVM fixture observations use the provider-specific fake observe transport
  boundary and synthetic fixture contracts.
- PiKVM screenshot results are metadata-only; raw image bytes are not returned
  by the scaffold.
- Provider results use the normalized provider result envelope.
- CLI/MCP equivalent requests are covered by a status consistency matrix.
- The MCP SDK adapter is mock-only by default and returns the same structured
  statuses through `MCPRouter`.
- The MCP host compatibility layer is mock-only, dependency-free, local, and
  routes through `MCPSDKAdapter`; it does not open a listener or call providers
  directly.
- Host tool schemas are JSON-safe and contain no secrets, live hostnames, live
  IP addresses, or credential examples.

## Deferred Work

- Live MCP SDK server adapter.
- MCP client integration tests.
- Live MCP host integration tests.
- Live provider MCP tests.
- Live PiKVM transport and live PiKVM MCP tests.
- Live operator approval transport.
- Live provider registry selection beyond disabled placeholders.

The MCP SDK adapter spec exists as docs-only research in
`specs/006-mcp-sdk-adapter/`. No SDK dependency or live server has been added.
