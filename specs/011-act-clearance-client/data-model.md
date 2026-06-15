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
- `risk_family` (required, explicit, non-null)
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
- `risk_family`
- `short_code`
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

## Risk Family Mirror

AgenticKVM labels the request; ACT owns tier and channel decisions.

- `low_risk`: observe/read capability labels.
- `high_risk`: consequential capability labels and any unmapped capability.

An unmapped capability must never omit `risk_family` and must never fall back to
a permissive value.
