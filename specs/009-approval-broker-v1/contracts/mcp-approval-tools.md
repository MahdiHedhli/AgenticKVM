# MCP Approval Tools Contract

MCP exposes exactly two approval verbs:

1. request approval
2. deny approval

MCP must not expose:

- grant approval
- approve approval
- sign grant
- consume grant
- edit approval cache

Any attempted MCP grant or approve tool name must fail closed as an unknown
tool or policy error.

Granting belongs only to trusted operator surfaces:

- host-native elicitation dialog
- out-of-band push channel
- watch TUI
- future trusted operator UI

MCP request approval output must include:

- request ID
- short code
- operator message
- risk summary
- retry instructions
- timeout behavior

No MCP tool call may block indefinitely.
