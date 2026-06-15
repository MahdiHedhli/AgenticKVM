# ACT Clearance Response Mirror

Canonical source: Agentic Control Tower. This AgenticKVM file is a client-side
mirror pending alignment with ACT's canonical clearance contract. It is not an AgenticKVM-owned response contract or proof format.

## Mirrored Expected States

- `clearance_required`
- `cleared`
- `denied`
- `expired`
- `invalid`
- `tower_unavailable`
- `verification_failed`

## Mirrored Expected Fields

- `request_id`
- `session_id`
- `target`
- `provider`
- `capability`
- `params_fingerprint`
- `risk_family`
- `short_code`
- `expires_at`
- `tower_id`
- `proof`
- `audit_correlation_id`
- `operator_message`
- `reason`

`risk_family` and `expires_at` must be present on poll/result shapes because
AgenticKVM acts on the ACT response. AgenticKVM verifies the returned
`risk_family`, `short_code`, and `params_fingerprint` against the original
request mirror before provider execution.

## Proof Handling

ACT owns the clearance proof/signature format. AgenticKVM treats proof
verification as a fail-closed client interface until ACT publishes the canonical
format. Mock proof verification is allowed only in tests.
