# ACT Clearance Request Mirror

Canonical source: Agentic Control Tower. This AgenticKVM file is a client-side
mirror pending alignment with ACT's canonical clearance contract. It is not an
AgenticKVM-owned wire contract.

## Mirrored Expected Fields

- `request_id`
- `aircraft`: `AgenticKVM`
- `session_id`
- `target`
- `provider`
- `capability`
- `params_fingerprint`
- `risk_family`
- `risk_summary`
- `operator_message`
- `requested_by`
- `created_at`
- `expires_at`
- `short_code`
- `policy_context`
- `audit_correlation_id`

## Rules

- Request parameters are represented by fingerprint and redacted preview, not
  raw secret-bearing payloads.
- `operator_message` tells the agent/model what to surface to the operator.
- AgenticKVM must update this mirror from ACT once the canonical contract lands.
