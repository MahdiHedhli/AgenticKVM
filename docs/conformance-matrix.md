# Host Conformance Matrix

AgenticKVM treats MCP host behavior as a published conformance matrix. The
project does not add bespoke host-specific provider paths. Every host must
preserve the same safety outcomes: policy first, approval as a first-class
result, signed broker grants before execution, and audit before provider
effects.

| Host | MCP initialize | Tool list | `readOnlyHint` | `destructiveHint` | Elicitation | `approval_required` rendering | `operator_message` rendering | stdio support | Timeout behavior | Scripted harness | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hermes | planned | planned | planned | planned | unknown | planned | planned | planned | must return within bounded wait | required | candidate scripted host |
| OpenClaw | planned | planned | planned | planned | unknown | planned | planned | planned | must return within bounded wait | required | candidate scripted host |
| Codex | planned | planned | planned | planned | unknown | planned | planned | planned | must return within bounded wait | required | model UI must surface operator message |
| Claude | planned | planned | planned | planned | unknown | planned | planned | planned | must return within bounded wait | required | generic Claude host row |
| Claude Code | planned | planned | planned | planned | worst-case | planned | planned | planned | must fall back to out-of-band approval | required | reference worst case |
| Codex CLI | planned | planned | planned | planned | unknown | planned | planned | planned | must return within bounded wait | required | CLI host must not grant approvals |
| Antigravity CLI | planned | planned | planned | planned | unknown | planned | planned | planned | must return within bounded wait | required | candidate scripted host |
| Grok Build | planned | planned | planned | planned | unknown | planned | planned | planned | must return within bounded wait | required | candidate scripted host |
| Claude Desktop | planned | planned | planned | planned | best-case | planned | planned | planned | native prompt may complete before timeout | required | reference best case |

## Required Outcomes

- Observe tools must advertise read-only intent where the SDK supports
  annotations.
- Power, input, boot, media, and mutation tools must advertise destructive
  intent where the SDK supports annotations.
- `approval_required` must remain visible and structured.
- `operator_message` must be available for model/chat rendering.
- No host may receive or expose an MCP grant tool.
- Host-native elicitation must fall back to out-of-band approval when
  unsupported or when the timeout is reached.
- Scripted harness coverage remains the conformance baseline until each host is
  manually reviewed.
