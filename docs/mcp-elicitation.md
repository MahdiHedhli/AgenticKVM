# MCP Elicitation

MCP host-native elicitation is an approval channel, not an authority boundary.
When an MCP host supports elicitation, AgenticKVM can ask the host to render an
operator prompt. The broker still owns approval state, signs grants, and the
control plane verifies the signed grant before provider execution.

## Capability Detection

Future live MCP SDK server work must detect elicitation support during MCP
initialize. If a host does not advertise or reliably complete elicitation, the
adapter falls back to out-of-band approval.

Reference hosts:

- Claude Desktop is the best-case host for native elicitation.
- Claude Code is the worst-case host and must be treated as possibly unable to
  complete native elicitation.

The compatibility matrix is published in [Conformance Matrix](conformance-matrix.md).

## Timeout Rule

No tool call may block indefinitely waiting for an approval prompt. The default
maximum wait is 20 seconds. If approval does not complete within that window,
the tool returns `approval_required` with:

- short code
- operator message
- human-readable risk summary
- retry instructions

The agent should surface the code to the operator and retry with identical
parameters after out-of-band approval.

## Trust Boundary

Native elicitation can collect operator intent, but it cannot execute providers
directly. A successful approval must become a broker-signed grant. Provider
execution still flows through:

```text
MCP host -> MCP router -> ControlPlane -> signed grant verifier -> provider adapter
```

MCP has only request and deny approval verbs. It never has a grant verb.
