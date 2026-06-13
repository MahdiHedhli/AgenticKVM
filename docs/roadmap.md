# Roadmap

AgenticKVM is an out-of-band control-plane project.

The current priority is not another public beta package, mock demo, or in-band
session provider. The priority is Approval Broker v1, signed grants,
out-of-band trust, and the path toward the killer demo: an agent recovering a
real wedged machine through the full approval chain.

## Locked Direction

1. AgenticKVM is out-of-band only.
2. Public beta is deferred behind the killer demo.
3. Approval authority is rebuilt around broker-owned signed grants.
4. MCP grants are forbidden. MCP may request approval or deny approval only.
5. Live providers remain disabled by default and excluded from CI.

## Active Provider Scope

Active AgenticKVM scope:

- KVM
- BMC
- PiKVM
- Redfish
- iLO
- iDRAC
- IPMI / Supermicro BMC
- policy, approval, audit, provider, and target registry control-plane logic

Parked scope:

- RustDesk
- VNC
- RDP
- MeshCentral
- BrowserBridge
- desktop/session brokers
- remote desktop/session providers

The parked scope is documented in
[Parking Lot: In-Band Remote Session Providers](parking-lot/inband-remote-session-providers.md).
It is not on the AgenticKVM roadmap.

## Current Order Of Work

### 1. Approval Broker v1

Implement broker-owned approval state, signed grants, parameter fingerprint
binding, expiry, one-time consumption, storage-as-cache semantics, out-of-band
approval channels, MCP request/deny-only tools, and ControlPlane verification
before provider execution.

Status: current sprint.

### 2. MCP Server On Official SDK

Live MCP SDK server and client integration deferred. Adopt the official Python
MCP SDK later on mainline, stdio transport first.

Keep CI mock-only.
HTTP and OAuth remain later work.

When MCP server work resumes:

- set tool annotations
- use `readOnlyHint` for observe tools
- use `destructiveHint` for power and other dangerous tools
- surface `operator_message` for chat rendering
- detect host elicitation capability at initialize time
- never block a tool call indefinitely
- route through the host compatibility and ControlPlane path

Status: deferred until Approval Broker v1 is merged and reviewed.

### 3. Live PiKVM Observe Slice

Implement the smallest disabled-by-default live PiKVM observe-only slice after
approval broker, audit, config, credential-reference, and manual smoke gates
are satisfied.

Allowed first-slice direction:

- provider health/status
- observe screen metadata
- screenshot artifact metadata where configured
- safe read-only power or boot status if available

Not allowed in the observe slice:

- keyboard
- mouse
- paste
- hotkeys
- power/reset
- virtual media
- boot changes
- firmware, BIOS, storage, network, or BMC account mutation

Status: not started.

### 4. Killer Demo

The launch-defining demo is an agent recovering a real wedged machine through
the full approval chain:

```text
agent request
-> MCP/CLI/control-plane entry
-> provider and target registry
-> policy decision
-> approval_required with short code and risk summary
-> broker-owned signed grant through trusted operator surface
-> ControlPlane verifies grant
-> provider observe/recovery action
-> audit evidence
-> operator-readable result
```

The demo must use explicit operator approval and must not rely on chat as the
trust anchor.

Status: blocked on Approval Broker v1 and live PiKVM observe.

### 5. Public Beta

Public beta is deferred until after the killer demo exists. A public beta that
announces mocks talking to mocks is not the project goal.

The conformance matrix, public site, release-quality checks, and beta docs stay
useful preparation, but they are not the beta launch gate.

Status: deferred.

## Completed Foundation

- constitution and spec discipline
- policy core and capability registry
- audit baseline and SQLite audit backend v1
- mock provider and fake/fixture observe paths
- provider and target registries
- CLI mock/fixture workflows
- dependency-free MCP scaffold and host compatibility layer
- local operator approval transport and console
- safe recovery playbook framework for mock/fake providers
- release-quality scripts, static site, and mock-only CI

## Safety Gates That Remain

- no real hardware in CI
- no live providers enabled by default
- no credential resolution in tests
- no MCP grant tool
- no approval authority from editable JSON files
- no provider execution without policy and signed grant verification where
  approval is required
- no live PiKVM input until a separate gated phase
- no public beta launch before the killer demo
