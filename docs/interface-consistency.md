# Interface Consistency

CLI and MCP are adapters, not authority boundaries. Equivalent requests for the
same target, tool, and mode must return the same status.

## Mock Target Matrix

| Mode | Observe tools | Power on | Graceful restart | Force restart | Boot override | Secret reveal | Policy modify |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Observe | `ok` | `denied` | `denied` | `denied` | `denied` | `denied` | `denied` |
| Assisted | `ok` | `approval_required` | `approval_required` | `denied` | `denied` | `denied` | `denied` |
| Supervised | `ok` | `approval_required` | `approval_required` | `approval_required` | `approval_required` | `denied` | `denied` |
| Full Control | `ok` | `ok` | `ok` | `ok` | `ok` | `denied` | `denied` |

Full Control bypasses prompts for in-scope mock actions, not hard invariants.
Raw secret reveal and policy self-modification remain denied by default.

Unknown tools return `validation_error` in both interfaces.
