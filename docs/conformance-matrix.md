# Host Conformance Matrix

AgenticKVM treats MCP host behavior as a published conformance matrix. The
project does not add bespoke host-specific provider paths. Every host must
preserve the same safety outcomes: policy first, approval as a first-class
result, ACT clearance before execution when policy requires it, and audit before
provider effects.

| Host | MCP initialize | Tool list | `readOnlyHint` | `destructiveHint` | `request_clearance` tool | `deny_clearance` tool | No grant tool | Elicitation detection | `clearance_required` rendering | `operator_message` rendering | stdio support | Timeout behavior | Out-of-band fallback | Scripted MCP harness | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hermes | planned | planned | planned | planned | required | required | required | unknown | planned | planned | planned | must return within bounded wait | required | required | candidate scripted host |
| OpenClaw | planned | planned | planned | planned | required | required | required | unknown | planned | planned | planned | must return within bounded wait | required | required | candidate scripted host |
| Codex | planned | planned | planned | planned | required | required | required | unknown | planned | planned | planned | must return within bounded wait | required | required | model UI must surface operator message |
| Claude | planned | planned | planned | planned | required | required | required | unknown | planned | planned | planned | must return within bounded wait | required | required | generic Claude host row |
| Claude Code | planned | planned | planned | planned | required | required | required | worst-case | planned | planned | planned | must fall back to out-of-band approval | required | required | reference worst case |
| Codex CLI | planned | planned | planned | planned | required | required | required | unknown | planned | planned | planned | must return within bounded wait | required | required | CLI host must not grant clearance |
| Antigravity CLI | planned | planned | planned | planned | required | required | required | unknown | planned | planned | planned | must return within bounded wait | required | required | candidate scripted host |
| Grok Build | planned | planned | planned | planned | required | required | required | unknown | planned | planned | planned | must return within bounded wait | required | required | candidate scripted host |
| Claude Desktop | planned | planned | planned | planned | required | required | required | best-case | planned | planned | planned | native prompt may complete before timeout | required | required | reference best case |

## Required Outcomes

- Observe tools must advertise read-only intent where the SDK supports
  annotations.
- Power, input, boot, media, and mutation tools must advertise destructive
  intent where the SDK supports annotations.
- `clearance_required` must remain visible and structured.
- `operator_message` must be available for model/chat rendering.
- No host may receive or expose an MCP grant, approve, clear, sign, or
  trust-signer tool.
- Host-native elicitation must fall back to out-of-band ACT clearance when
  unsupported or when the timeout is reached.
- Scripted harness coverage remains the conformance baseline until each host is
  manually reviewed.
