# Data Model: Control Plane

## Capability

- id: stable provider-neutral identifier, such as `power.force_off`
- family: one of the required capability families
- action: provider-neutral action name
- title: human-readable label
- description: concise behavior description
- risk: `low`, `medium`, `high`, or `critical`
- dangerous: whether Supervised mode must gate the action
- destructive: whether the action can destroy data or availability
- required_scope: target, session, credential, or parameter scope required
- audit_fields: fields that must be present when requested

## Capability Request

- id
- correlation_id
- session_id
- requester
- target
- capability
- parameters
- intended_effect
- created_at

## Policy

- version
- name
- mode
- defaults
- target_scope
- session_scope
- decisions
- limits
- approval_rules
- invariant_overrides: prohibited by default; any future use requires a
  constitution amendment

## Policy Decision

- decision: `deny`, `ask_each_time`, `ask_once_per_session`, `allow`, or
  `allow_with_limits`
- reason
- matched_rule
- limits
- requires_approval
- material_risks

## Approval Request

- id
- capability
- action
- target_scope
- session_id
- requester
- policy_decision
- operator_message
- material_risks
- expires_at
- proposed_audit_event_id

## Provider Adapter

- id
- kind
- version
- supported_capabilities
- is_real_hardware
- execute_authorized(request)

Provider adapters do not contain mode policy or approval logic.

## Audit Event

- id
- timestamp
- event_type
- correlation_id
- session_id
- target_id
- actor
- capability
- policy_decision
- approval
- provider
- request
- result
- redactions
- material_risks

Audit events must be structured and secret-redacted by default.
