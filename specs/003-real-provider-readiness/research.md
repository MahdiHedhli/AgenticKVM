# Research Notes

## Lessons From Donor Spike

The donor `Agentic-KVM` repo shows useful provider ideas for PiKVM, Redfish,
IPMI, and Supermicro, but its architecture is not authoritative. Provider work
must be redesigned through AgenticKVM's capability registry, policy engine,
approval model, audit model, provider registry, and target registry.

## Readiness Findings

- Read-only provider calls still carry risk because inventory, event logs,
  screenshots, and sensor data may reveal sensitive operational context.
- Redfish and BMC capability support varies by hardware, license, and privilege.
- Screenshots can reveal secrets and must be treated as observable sensitive
  data.
- Provider-specific reset, boot, firmware, storage, and BMC actions must never
  be collapsed into generic low-risk actions.

## Dependency Decision

No provider SDK dependency is selected by this spec. Provider-specific specs
must justify dependencies before implementation.
