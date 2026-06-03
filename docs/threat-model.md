# Threat Model

## Assets

- real machines
- BMC, KVM, Redfish, and PiKVM endpoints
- credentials and secret references
- operator approval decisions
- audit artifacts
- policy documents
- target and session scope

## Adversaries And Failure Modes

- prompt injection in agent context
- mistaken agent planning
- malicious or compromised tool input
- overbroad operator approval
- provider API ambiguity
- stale or incorrect target mapping
- leaked credentials
- audit tampering
- unsafe migration from donor spike code

## Primary Risks

- unintended power disruption
- data loss through storage operations
- firmware or BIOS misconfiguration
- booting from untrusted media
- BMC lockout or credential compromise
- secret exposure
- external system calls outside operator intent
- agent self-escalation
- audit gaps after destructive actions

## Mitigations

- policy as authority boundary
- default-deny unknown capabilities
- explicit target and session scope
- dangerous action gates in Supervised mode
- Full Control hard invariants
- mock-only CI
- mandatory structured audit
- secret redaction by default
- provider adapters without policy ownership
- donor-spike inventory before migration

## Open Threat Model Work

- Add STRIDE-style scenarios per capability family.
- Add provider-specific risk reviews for PiKVM and Redfish.
- Define emergency stop implementation requirements.
- Define audit retention and tamper-evidence requirements.
- Define lab-only real hardware validation process.
