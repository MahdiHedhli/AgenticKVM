# Tasks: Redfish Observe-Only Provider

- [x] Write provider-specific observe-only spec.
- [x] Add fake transport client contract.
- [x] Add fixture-backed Redfish observe client tests.
- [x] Add disabled-by-default provider adapter.
- [x] Add config placeholder with no secrets.
- [x] Add CLI/MCP fake-provider integration tests.
- [x] Add manual smoke documentation for future live testing.
- [x] Update provider readiness matrix.
- [ ] Write Redfish live observe ADR after PiKVM observe transport boundary is
  proven.
- [ ] Keep first Redfish live slice GET-only; do not implement POST, PATCH,
  DELETE, action URIs, virtual media, boot override, account changes, network
  changes, storage actions, firmware updates, or secret reveal.
- [ ] Reuse the fake-first transport injection and fixture contract pattern
  before any live Redfish network code.
