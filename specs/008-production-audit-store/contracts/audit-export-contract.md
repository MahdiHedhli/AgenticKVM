# Audit Export Contract

## Purpose

Audit export bundles allow offline investigation and verification without live
services or production credentials.

## Bundle Contents

- version
- export id
- created timestamp
- audit log id
- redacted audit records
- optional checkpoint
- chain verification result
- checkpoint verification result
- record count
- last event hash
- redaction summary
- metadata

## Verification

Import/verify must:

- validate JSON-safe structure
- verify the audit hash chain
- verify checkpoint if present
- detect tampered events
- detect missing middle events
- detect tail truncation when checkpoint data is present
- fail closed on malformed bundles

## Prohibited Contents

- raw secrets
- raw credentials
- unredacted credential refs
- raw screenshot bytes
- raw image fields
- raw provider credentials
- live hostnames or IPs in test fixtures
