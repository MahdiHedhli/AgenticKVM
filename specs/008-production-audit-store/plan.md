# Implementation Plan: Production Audit Store

## Approach

Build the smallest mock-safe audit hardening layer around the existing local
JSONL sink:

1. Document production requirements and non-goals.
2. Add a local checkpoint model that records event count and last event hash.
3. Add export/import verification helpers for JSON-safe audit bundles.
4. Add a retention/rotation policy model that rejects silent deletion.
5. Define audit failure behavior and high-risk fail-closed expectations.
6. Add host-level conformance fixtures.
7. Update MCP/server dependency review docs so future live adapters preserve
   audit behavior.

## Constraints

- No live MCP server.
- No real MCP SDK dependency.
- No live provider behavior.
- No hardware or live network calls.
- No secrets or credential resolution.
- Tests use temporary directories only.

## Verification

- `uv run --with pytest --python python3.13 python -m pytest`
- Unit tests for checkpoint and retention models.
- Contract tests for export/import verification.
- Security tests for redaction and audit failure behavior.
- Host conformance tests for audit lifecycle coverage.
