# Approval Broker v1 Data Model

## Approval Request

- request ID
- session ID
- target
- provider
- capability
- parameter fingerprint
- risk family
- channel
- short code
- operator message
- risk summary
- created timestamp
- expiry timestamp

## Approval Grant

- grant ID
- request ID
- session ID
- target
- provider
- capability
- parameter fingerprint
- risk family
- channel
- expires at
- one-time flag
- consumed at
- policy channel constraints
- signer key ID
- canonical payload version

## Signed Approval Grant

- grant payload
- signer key ID
- signature algorithm
- signature

## Verification Result

- status: valid, rejected, expired, consumed, malformed, unsigned
- reason
- request ID
- grant ID
- signer key ID
- consumed flag

## Cache Record

- approval request cache entry
- signed grant cache entry
- denial cache entry
- redaction metadata

Cache records are not authority without a valid signed grant.
