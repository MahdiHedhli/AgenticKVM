# Roadmap

AgenticKVM is an out-of-band control-plane project.

The current priority is not another public beta package, mock demo, or in-band
session provider. The priority is the ACT clearance client boundary and the path
toward the killer demo: an agent recovering a real wedged machine through the
full Agentic Control Tower clearance chain.

## Locked Direction

1. AgenticKVM is out-of-band only.
2. Public beta is deferred behind the killer demo.
3. AgenticKVM consumes ACT clearance; ACT owns signing, mobile approval, replay
   defense, clearance audit, and one-time clearance consumption.
4. MCP grants are forbidden. MCP may request clearance or deny clearance only.
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

### 1. ACT Clearance Client Boundary

Implement the control-plane-to-tower seam. AgenticKVM mirrors ACT clearance
request/response expectations until ACT publishes the canonical contract, calls
ACT when local policy requires clearance, verifies tower responses through a
fail-closed client seam, and proceeds only on verified `cleared` responses.

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
-> clearance_required with short code and risk summary
-> ACT pushes approval to the operator phone
-> operator clears through trusted mobile approval
-> ControlPlane verifies ACT clearance response
-> provider observe/recovery action
-> audit evidence
-> operator-readable result
```

The demo must use explicit operator approval and must not rely on chat as the
trust anchor.

Status: blocked on ACT clearance client boundary and live PiKVM observe.

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
- Approval Broker v1 dev/test scaffold proving file queues are not authority
- safe recovery playbook framework for mock/fake providers
- release-quality scripts, static site, and mock-only CI

## Safety Gates That Remain

- no real hardware in CI
- no live providers enabled by default
- no credential resolution in tests
- no MCP grant/approve/clear tool
- no approval or clearance authority from editable JSON files
- no provider execution without policy and verified ACT clearance where
  clearance is required
- no live PiKVM input until a separate gated phase
- no public beta launch before the killer demo
