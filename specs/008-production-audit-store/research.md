# Research: Production Audit Store

## Current Local Behavior

The current `LocalJSONLAuditSink` appends redacted JSONL records. Each record
stores:

- `previous_hash`
- redacted `event`
- `event_hash`

This detects content tampering, middle-event deletion, and event reordering.
It cannot detect tail truncation without a trusted checkpoint that records the
latest event count and last event hash outside the log.

## Production Options To Evaluate Later

- local append-only file plus external checkpoint
- OS-protected append-only storage
- database-backed audit store
- object storage with versioning and retention lock
- SIEM/export pipeline
- hardware-backed or externally signed checkpoints

## Deferred Research

- production storage backend
- checkpoint signing
- operator identity backend
- retention law/compliance needs
- cloud/SIEM integration
- live MCP server logging behavior
