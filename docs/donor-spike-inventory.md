# Donor Spike Inventory Template

The old `Agentic-KVM` repository is a donor spike used for lessons. It is not an
authoritative architecture source for AgenticKVM.

Use this template to inventory donor behavior before migrating any idea into the
canonical repository.

## Inventory Item

- donor location:
- observed behavior:
- capability family:
- proposed AgenticKVM capability id:
- target scope required:
- session scope required:
- dangerous action:
- destructive action:
- required policy decision:
- approval explanation:
- audit fields:
- secret handling:
- provider contract impact:
- mock behavior:
- tests required:
- migration decision: keep, redesign, defer, or discard
- notes:

## Review Questions

- Does this behavior require provider access?
- Can it be expressed as a provider-neutral capability?
- Does it bypass policy in the donor spike?
- Does it reveal secrets?
- Does it modify power, boot, BIOS, firmware, storage, network, BMC, or
  credentials?
- Does it need real hardware to test, or can it be mocked?
- What would make the behavior safe enough for mass consumption?
