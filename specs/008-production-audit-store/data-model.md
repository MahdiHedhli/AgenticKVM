# Data Model: Production Audit Store

## Audit Checkpoint

- `checkpoint_id`: stable checkpoint identifier
- `audit_log_id`: identifier for the audit log being checkpointed
- `last_event_index`: zero-based index of the last checkpointed event
- `event_count`: number of checkpointed events
- `last_event_hash`: hash of the last checkpointed event
- `previous_checkpoint_hash`: optional hash linking to a previous checkpoint
- `created_at`: checkpoint creation timestamp
- `metadata`: redacted JSON-safe metadata
- `checkpoint_hash`: hash over canonical checkpoint content

## Audit Export Bundle

- `version`
- `export_id`
- `created_at`
- `audit_log_id`
- `records`
- `checkpoint`
- `chain_verified`
- `checkpoint_verified`
- `record_count`
- `last_event_hash`
- `redaction_summary`
- `metadata`

## Retention Policy

- `policy_id`
- `max_event_count`
- `max_log_bytes`
- `max_age_days`
- `rotation_requires_checkpoint`
- `rotation_requires_verified_archive`
- `allow_silent_deletion`
- `archive_metadata`

Silent deletion is invalid by default.
