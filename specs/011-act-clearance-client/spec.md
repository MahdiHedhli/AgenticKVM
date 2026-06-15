# Spec 011: ACT Clearance Client

## Scope

This spec describes AgenticKVM as a client of Agentic Control Tower (ACT).
ACT owns the canonical clearance request, response, and proof contract.
AgenticKVM mirrors the expected contract shape only until ACT publishes the
canonical spec.

## Goal

Show the control-plane-to-tower call boundary first:

```text
local policy requires clearance
-> AgenticKVM requests ACT clearance
-> ACT returns clearance_required, cleared, denied, or failure state
-> AgenticKVM verifies the tower response as a client
-> AgenticKVM executes only on verified cleared response
```

## Non-Goals

- No local production approval signing.
- No AgenticKVM-owned clearance wire contract.
- No invented clearance proof or signature format.
- No MCP grant, approve, clear, sign, or trust-signer tool.
- No live provider execution.

## Requirements

- AgenticKVM must fail closed when ACT is unavailable or verification fails,
  except where policy explicitly allows returning `clearance_required`.
- AgenticKVM must keep local capability resolution, policy decision, provider
  and target registry validation, provider execution, local audit, and
  fail-closed behavior.
- ACT must remain the production authority for signing, mobile approval,
  clearance audit, replay defense, and one-time clearance consumption.
- The client timeout defaults to 20 seconds and must be configurable.
- Every AgenticKVM-built clearance request must include explicit non-null
  `risk_family`; missing capability mappings resolve to the restrictive
  `high_risk` family.
- AgenticKVM does not choose ACT operator channel or tier from `risk_family`.
- `operator_message` must be suitable for model/chat rendering and must not
  contain the double-period defect.

## Status

Proposed client boundary. Pending alignment with ACT's canonical clearance
contract and proof format.
