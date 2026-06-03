# Data Model: PiKVM Observe-Only Provider

## PiKVM Provider Config

- provider_id: stable configured provider id
- provider_type: `pikvm`
- enabled: false by default
- fixture_mode: true only in tests
- endpoint_reference: non-secret placeholder for future live config
- timeout_seconds: local timeout policy for future network calls
- tls_verify: documented future TLS verification preference

## PiKVM Target

- target_id
- provider_id
- enabled
- allowed_modes
- risk_tier
- labels
- metadata without secrets

## PiKVM Observation Result

- capability
- provider_id
- target_id
- performed_on_hardware: false in tests
- data: redacted provider-neutral observation
- source: fake transport, fixture, or future live endpoint

## Fake Transport Request

- method: `GET`
- path
- params
- timeout_seconds

No fake transport request may include credentials.
