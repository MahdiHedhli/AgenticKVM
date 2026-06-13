# Approval Broker v1 Plan

## Sequence

1. Reset roadmap and public docs to out-of-band only.
2. Define signed grant contract and approval channel policy.
3. Implement signed grant models and parameter fingerprinting.
4. Add a development/test signer abstraction.
5. Add signed cache storage with atomic writes, advisory lock, and `0600`
   permissions.
6. Add short-code approval request flow.
7. Restrict MCP approval verbs to request and deny.
8. Wire signed grant verification into `ControlPlane`.
9. Add notifier abstraction and a fake/local notifier for safe tests.
10. Add operator watch/list/allow/deny CLI surface.
11. Document host-native elicitation detection and conformance matrix.

## Safety Gates

- No live providers.
- No real hardware.
- No credentials.
- No MCP grant tool.
- No trusted authority from editable files.
- No tool call waits beyond the default timeout.

## Deferred

- keychain signer with user presence
- separate-UID daemon signer
- remote broker
- live MCP SDK server
- live PiKVM observe
- public beta launch
