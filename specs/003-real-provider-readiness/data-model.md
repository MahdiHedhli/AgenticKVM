# Data Model

## Provider Readiness Record

- provider type
- provider id
- enabled state
- real hardware flag
- supported capabilities
- observe-only capability set
- disabled dangerous capability set
- timeout policy
- error behavior
- audit behavior
- redaction behavior
- manual smoke status

## Target Readiness Record

- target id
- provider id
- environment
- risk tier
- allowed modes
- real hardware allowed flag
- manual smoke scope
- secret reference names only

## Manual Smoke Record

- operator id
- target id
- provider id
- session id
- capability
- expected observation
- expected audit artifact
- approval evidence
- rollback or stop criteria

## Forbidden Fields

Readiness records must not contain passwords, tokens, API keys, private keys,
session cookies, bearer values, raw credentials, or raw secret material.
