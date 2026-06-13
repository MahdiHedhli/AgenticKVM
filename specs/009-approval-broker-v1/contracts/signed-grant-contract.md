# Signed Grant Contract

The signed grant contract defines the only approval artifact that can authorize
provider execution after policy returns an approval-required decision.

## Canonical Payload

The canonical payload must be JSON serialized with sorted keys and compact
separators. The payload version is included in the signed data.

Required signed fields:

- `payload_version`
- `grant_id`
- `request_id`
- `session_id`
- `target`
- `provider`
- `capability`
- `params_fingerprint`
- `risk_family`
- `channel`
- `expires_at`
- `one_time`
- `consumed_at`
- `policy_constraints`
- `signer_key_id`

## Verification

Verification fails closed unless all checks pass:

- signature is valid
- signer key ID is trusted by the verifier
- request ID matches
- session ID matches
- target matches
- provider matches
- capability matches
- parameter fingerprint matches
- risk family matches
- channel is allowed for the risk family
- current time is before expiry
- one-time grant is not consumed
- hard invariant capability is not being approved

## Cache Semantics

Editing a cache file must never create authority. Unsigned, malformed, expired,
consumed, tampered, mismatched, or wrong-key grants fail closed.
