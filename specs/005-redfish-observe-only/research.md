# Research: Redfish Observe-Only Provider

## Provider Lessons

The donor spike showed that Redfish is useful for power state, health, thermal
data, power readings, firmware versions, event logs, storage inventory, and BMC
configuration observations. It also showed that reset, virtual media, boot,
firmware, event clearing, account, and webhook operations need explicit danger
classification.

## GET-Only Boundary

The first live Redfish slice must use only read requests. Any POST, PATCH,
DELETE, action URI invocation, or task that mutates BMC or host state is outside
this spec.

## Vendor Variation

Redfish implementations vary by vendor, generation, license, and privilege.
Provider results should degrade cleanly and return structured unavailable
fields instead of assuming a capability is present.

## Deferred Questions

- Which vendor-specific Redfish fields should be normalized first?
- Should event logs be summarized, paged, or returned as redacted entries?
- How should certificate pinning be represented in canonical config?
