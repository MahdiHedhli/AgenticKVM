# ACT Clearance Client Data Model

The canonical data model is owned by Agentic Control Tower. This file documents
AgenticKVM's client-side mirror expectations pending alignment with ACT's
published spec.

## ClearanceRequest Mirror

- `request_id`
- `aircraft`
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

## ClearanceResponse Mirror

- `status`
- `request_id`
- `session_id`
- `target`
- `provider`
- `capability`
- `params_fingerprint`
- `expires_at`
- `tower_id`
- `proof`
- `audit_correlation_id`
- `operator_message`
- `reason`

## Verification Result

- `valid`
- `status`
- `reason`
- `tower_id`
- `request_id`
