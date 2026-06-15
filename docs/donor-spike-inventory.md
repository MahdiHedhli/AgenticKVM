# Donor Spike Inventory: Agentic-KVM

## Purpose

This document inventories useful lessons from the original `Agentic-KVM` donor
spike for the canonical `AgenticKVM` implementation.

`Agentic-KVM` was the original dogfood spike used to validate agentic
out-of-band control in a real homelab. `AgenticKVM` is the canonical,
spec-driven implementation intended for broader use.

The donor spike may inform implementation, but it is not authoritative for:

- architecture
- public API
- safety model
- policy model
- approval behavior
- provider contract
- release quality bar

Inventory date: 2026-06-03.

Donor repo inspected read-only at `/Users/mhedhli/Documents/Coding/Agentic-KVM`
on branch `feat/redfish-backend-x10`.

## Classification Legend

- preserve: concept appears compatible with AgenticKVM after spec alignment
- redesign: useful behavior exists, but must be reworked through the control
  plane
- defer: useful later, but blocked by earlier maturity gates
- reject: should not be carried forward
- unknown: needs more review before classification

## Useful Concepts To Preserve

| Concept | Donor evidence | New classification | Notes |
| --- | --- | --- | --- |
| Explicit control modes and capability decisions | `src/pikvm_mcp/policy.py`, `tests/test_policy.py` | preserve | Aligns with the new constitution; naming and schema should be adapted to AgenticKVM contracts. |
| Unknown capability default deny | `tests/test_policy.py` | preserve | Already matches the core safety model. |
| Hard denial of policy self-modification and raw secret reveal | `src/pikvm_mcp/policy.py` | preserve | Broaden into hard invariant enforcement rather than only a hard deny list. |
| Target allow/deny scope | `TargetPolicy` and policy tests | preserve | Expand into target and session scope models. |
| Redacted audit arguments | `src/pikvm_mcp/audit.py`, `tests/test_audit.py` | preserve | Replace tool-wrapper audit with structured control-plane audit events. |
| Certificate fingerprint pinning | PiKVM, Redfish, and Supermicro clients plus cert tests | preserve | Useful provider-readiness lesson; keep disabled-by-default provider configs. |
| License-gated Redfish behavior | Redfish client and DCMS tool tests | preserve | Convert into provider capability metadata and explainable unavailable-provider results. |
| Live integration tests gated by environment flags | `tests/integration/conftest.py` | preserve | Keep real hardware tests opt-in and outside CI. |
| Router preference/fallback between Redfish and IPMI for reads | `tools/router.py`, `tests/test_router.py` | redesign | Useful behavior, but routing must be a provider decision after policy, not a tool shortcut. |
| Safe target inventory that omits secrets | `agentic_kvm_targets` tests | preserve | Rebuild as an observe capability and config summary. |

## Port This: PiKVM Provider Controls

These donor-spike items are AgenticKVM-specific provider knowledge and should be
ported into future PiKVM provider slices. They do not live in ACT.

### PiKVM Cert-Pinning Preflight

Port target: PiKVM live transport.

When `cert_fingerprint` is configured, the PiKVM transport must open an
unauthenticated TLS connection first and verify the presented certificate
fingerprint before sending credentials. Only after the fingerprint matches may
the authenticated client be constructed, trusting that pinned certificate as the
sole trust root.

This preserves the donor reasoning that `verify_ssl: false` for self-signed
PiKVM can be intentional only when paired with certificate pinning. Credentials
must not go over the wire on certificate mismatch.

### HID Text Redaction With Explicit Full-Capture Opt-In

Port target: redaction overhaul and future PiKVM input phase.

Typed HID text is redacted by default because it may contain passwords, BIOS
fields, recovery keys, disk unlock strings, and other sensitive material. Full
capture requires explicit opt-in such as `PIKVM_FULL_CAPTURE`. Credential fields
remain stripped even under full capture.

### Real PiKVM Tool Surface And Screenshot Mouse Calibration

Port target: PiKVM live provider capability map and later gated input phase.

The donor MSD, ATX, and HID breakdown is the live PiKVM provider capability map
reference. Screenshot-based absolute mouse calibration matters for real PiKVM
input later and should be preserved in the provider design, fake tests, and
manual smoke plans before any live input is attempted.

## Provider Code Worth Reviewing

| Provider area | Donor files | Classification | Capability families |
| --- | --- | --- | --- |
| PiKVM HTTP client | `src/pikvm_mcp/client.py` | defer | observe, input, media, power |
| PiKVM HID tools | `src/pikvm_mcp/tools/hid.py` | redesign | observe, input |
| PiKVM streamer tools | `src/pikvm_mcp/tools/streamer.py` | redesign | observe, runtime |
| PiKVM MSD tools | `src/pikvm_mcp/tools/msd.py` | redesign | media, boot |
| PiKVM ATX tools | `src/pikvm_mcp/tools/atx.py` | redesign | power |
| Redfish client | `src/pikvm_mcp/redfish_client.py` | defer | observe, power, boot, bmc, firmware, storage, network |
| Redfish tool wrappers | `src/pikvm_mcp/tools/redfish.py`, `redfish_dcms.py` | redesign | observe, power, boot, bmc, firmware, storage, network |
| IPMI client | `src/pikvm_mcp/ipmi_client.py` | defer | observe, power, bmc |
| IPMI tool wrappers | `src/pikvm_mcp/tools/ipmi.py` | redesign | observe, power |
| Supermicro legacy web client | `src/pikvm_mcp/supermicro_client.py` | defer | media, observe |
| Supermicro iKVM bridge | `src/pikvm_mcp/bridge.py`, `docker/supermicro-ikvm-bridge/` | defer | observe, runtime |

No provider implementation should be copied directly. Each provider behavior
must earn its way in through capability specs, mock behavior, policy gates,
approval behavior, audit events, and contract tests.

## MCP Tool Names And Behavior Worth Preserving

These donor tool names are useful as compatibility references. New AgenticKVM
tools may expose different names if the capability model requires it.

| Donor tool | Family | Classification | Notes |
| --- | --- | --- | --- |
| `agentic_kvm_targets` | observe | preserve | Must expose non-secret target context only. |
| `pikvm_msd_state` | media | redesign | Safe observe capability. |
| `pikvm_msd_upload_url` | media | redesign | Requires URL allowlist and approval model before implementation. |
| `pikvm_msd_set_image` | media | redesign | Requires approved media scope. |
| `pikvm_msd_connect` / `pikvm_msd_disconnect` | media | redesign | Mount/eject must be capability-gated. |
| `pikvm_atx_state` | power | redesign | Observe-only power state is low risk. |
| `pikvm_atx_power_on` | power | redesign | Requires explicit scope and audit. |
| `pikvm_atx_power_off_hard` | power | redesign | Dangerous action; gated in Supervised. |
| `pikvm_atx_reset` | power | redesign | Dangerous action; gated in Supervised. |
| `pikvm_hid_state` | observe/input | redesign | Safe observe portion should be separated from input actions. |
| `pikvm_screenshot` | observe | preserve | Mock first; secrets and screen content handling need audit policy. |
| `pikvm_hid_type` | input/secrets | redesign | Typed text may contain secrets; default audit redaction required. |
| `pikvm_hid_send_key` / `pikvm_hid_shortcut` | input | redesign | Safe key vs dangerous hotkey split required. |
| `pikvm_mouse_move` / `pikvm_mouse_click` / `pikvm_mouse_scroll` | input | redesign | Supervised mode may allow scoped low-risk input. |
| `pikvm_hid_calibrate` | observe/input | preserve | Useful for mock and PiKVM provider parity. |
| `pikvm_streamer_state` | observe | preserve | Safe observe behavior. |
| `pikvm_wake_host` | runtime/power | redesign | Must not become implicit power control. |
| `ipmi_power_state` | observe/power | preserve | Read-only power state is a high-priority real provider readiness target. |
| `ipmi_health` / `ipmi_sensors` | observe | preserve | Good observe capability candidates. |
| `ipmi_event_log` | observe | preserve | Audit and event-log normalization useful. |
| `ipmi_inventory` / `ipmi_firmware` | observe | preserve | Read-only inventory candidates. |
| `ipmi_system_power_watts` | observe | preserve | Should degrade cleanly on privilege limits. |
| `ipmi_power_on` / `ipmi_power_shutdown` / `ipmi_power_off` / `ipmi_power_reset` | power | redesign | Must route through policy and approval. |
| `supermicro_vm_status` / `supermicro_vm_config_get` | observe/media | preserve | Read-only legacy web lessons. |
| `supermicro_vm_config_set` / `supermicro_vm_mount` / `supermicro_vm_unmount` | media | redesign | Virtual media mutation requires explicit scope. |
| `supermicro_ikvm_jnlp` / `supermicro_ikvm_prepare_bundle` | observe/runtime | defer | Bridge artifacts need security review before reuse. |
| `supermicro_ikvm_launch_bridge` / `supermicro_ikvm_stop_bridge` | runtime | defer | Local container lifecycle must be logged and scoped. |
| `redfish_capabilities` | observe | preserve | Provider capability probe should be a first-class concept. |
| `redfish_firmware_versions` / `redfish_thermal` / `redfish_power` | observe | preserve | Read-only provider slice candidates. |
| `redfish_system_reset` | power | redesign | Dangerous action; exact reset type matters. |
| `redfish_boot_override` | boot | redesign | Dangerous action; must require explicit scope. |
| `redfish_fan_mode_get` / `redfish_mouse_mode_get` / `redfish_ntp_get` | observe | preserve | Read-only BMC config observations. |
| `redfish_fan_mode_set` / `redfish_mouse_mode_set` / `redfish_ntp_set` | bmc/network | redesign | BMC config mutations require approval and limits. |
| `redfish_event_log` | observe | preserve | Useful normalized event-log behavior. |
| `redfish_event_clear` | bmc | redesign | Clearing logs is dangerous because it can destroy evidence. |
| `redfish_macs` / `redfish_processors` / `redfish_memory` | observe | preserve | Inventory capability candidates. |
| `redfish_account_list` | observe/bmc | redesign | Account summaries must not reveal secrets. |
| `redfish_event_subscribe` / `redfish_event_unsubscribe` | bmc/network/runtime | redesign | External callback/webhook effects require explicit approval. |
| `redfish_bmc_reset` | bmc/power | redesign | Dangerous action; gated in Supervised. |
| `redfish_chassis_intrusion_clear` | bmc | redesign | Evidence-impacting action; approval required. |
| `redfish_ikvm_url` | observe/runtime | defer | License-gated and potentially sensitive access URL. |
| `redfish_vm_iso_mount` / `redfish_vm_iso_unmount` / `redfish_vm_status` | media | redesign | Arbitrary ISO mount is dangerous. |
| `redfish_simple_update` | firmware | redesign | Firmware update is dangerous. |
| `redfish_ssl_cert_upload` | bmc/network | redesign | BMC trust change requires explicit approval. |
| `redfish_storage` | storage | preserve | Read-only storage inventory first; mutations remain gated. |

## Docs Worth Porting

| Donor doc | Classification | Notes |
| --- | --- | --- |
| `docs/control-plane.md` | redesign | Earlier control-plane thinking, but new constitution wins. |
| `docs/security-model.md` | redesign | Useful safety gaps and redaction ideas. |
| `docs/control-plane-roadmap.md` | redesign | Mine tasks, not architecture. |
| `docs/adr/0001-agentic-kvm-control-plane.md` | redesign | Historical context only. |
| `docs/supermicro-ipmi.md` | defer | Provider-specific lessons for future Supermicro/IPMI specs. |
| `docs/supermicro-legacy-web.md` | defer | Legacy web provider notes for later provider design. |
| `docs/supermicro-ikvm-bridge.md` | defer | Requires runtime/container threat review. |
| `docs/kali-rpi4-pikvm-port.md` | unknown | Review later for install notes only. |
| `recipes/boot_from_iso.md` | redesign | Boot/ISO operations are dangerous and need new approval framing. |

## Install Notes Worth Porting

- Environment-file based local configuration is useful, but the canonical names
  should become `AGENTICKVM_*`.
- Example configs should use placeholders only and must not encourage default
  admin credentials.
- Certificate pinning notes are worth preserving.
- Runtime directory and audit directory configuration are worth preserving.
- Live integration environment flags are worth preserving as opt-in lab-only
  controls.
- Redfish/Supermicro license notes are worth preserving for provider docs.

## Config Patterns Worth Preserving

| Donor pattern | Classification | AgenticKVM direction |
| --- | --- | --- |
| JSON list of targets in env vars | redesign | Prefer config files plus env overrides; keep JSON examples only if validated. |
| Separate PiKVM and IPMI target lists | redesign | Use provider-neutral target registry with provider-specific connection blocks. |
| Default target selection | preserve | Must be explicit in session scope for mutating actions. |
| Secret fields as structured secret types | preserve | Keep raw secrets out of logs and model outputs. |
| `PIKVM_FULL_CAPTURE=false` default | preserve | New default must redact typed text and secrets. |
| `PIKVM_ENV_FILE` loading | redesign | Use `AGENTICKVM_CONFIG` and avoid loading secrets by default in tests. |

## Tests Worth Porting

| Donor test area | Classification | New test target |
| --- | --- | --- |
| Policy decisions by mode | preserve | Maturity 1 policy core. |
| Unknown capability denial | preserve | Already started; expand with registry tests. |
| Audit redaction | preserve | Maturity 2 audit core. |
| Config parsing and target resolution | preserve | Maturity 1 target/session scope. |
| Provider client HTTP behavior with mocked transports | defer | Real provider readiness. |
| Certificate pinning | defer | Provider readiness security tests. |
| Redfish license and privilege errors | defer | Provider readiness contract tests. |
| Router fallback behavior | redesign | Provider routing after policy only. |
| Live integration tests with opt-in flags | preserve | Lab-only, never CI default. |
| HID calibration and screenshot tests | defer | Mock provider first, PiKVM later. |

## Known Safety Gaps

- MCP tools are close to provider clients; new AgenticKVM must prevent direct
  tool-to-provider execution.
- Donor audit wraps tool calls, but the new project requires structured audit
  for capability request, policy decision, approval, provider execution, and
  result.
- Some donor mutating tools appear discoverable and callable without the new
  approval model.
- Redfish/IPMI/Supermicro reset, virtual media, boot override, firmware,
  account, event clearing, NTP, and webhook actions need stronger dangerous
  action classification.
- Raw target connection configuration is environment-driven; new config must be
  validated and secret-safe.
- Live tests exist and are gated, but they must remain outside canonical CI.
- Full Control in donor policy allows most known capabilities except hard denies;
  new Full Control must also enforce target scope, session scope, audit,
  emergency stop, secret handling, and provider-specific risk.

## Known Architectural Issues

- Provider routing and fallback are embedded near tool/provider layers rather
  than a central control-plane request lifecycle.
- Policy is scaffolded but not authoritative over every donor tool path.
- Capability registry is hard-coded in policy source rather than a structured
  registry contract.
- Provider-specific operations can be exposed as tool names before provider
  contracts define risk, audit, and approval semantics.
- Config names retain the donor `PIKVM_*` identity.

## Known Provider Limitations

- Supermicro Redfish DCMS/iKVM/media/update/storage features may require
  license activation.
- Redfish capabilities vary by BMC generation and privilege level.
- IPMI DCMI power readings can fail under lower privilege accounts.
- Supermicro legacy web flows require CSRF/session handling and may need
  generous timeouts.
- iKVM bridge behavior uses local container/runtime artifacts and needs separate
  threat modeling.
- PiKVM screenshot/HID/MSD behavior depends on video state, streamer state, and
  device mode.

## Behavior That Should Not Be Preserved

| Behavior | Classification | Reason |
| --- | --- | --- |
| Direct MCP tool calls to provider clients | reject | Violates the core architecture rule. |
| Provider/client code deciding effective safety | reject | Provider adapters do not own policy. |
| Any default real hardware tests | reject | Real hardware is never used in CI. |
| Default credentials in examples as plausible values | reject | Public examples should use placeholders and secret references. |
| Clearing BMC/event logs as a routine operation | reject | Evidence-impacting behavior must be high risk and gated. |
| Treating Redfish reset or boot actions as generic power actions | reject | Provider-specific reset/boot risk must stay explicit. |
| Raw secret or HID text capture by default | reject | Secrets are never revealed by default. |

## Candidate Compatibility Shims

- Donor MCP tool names can map to provider-neutral capability ids after Maturity
  4, but each shim must route through the control plane.
- `PIKVM_*` environment variables may be read only by an explicit migration
  helper, never as the canonical config namespace.
- Donor target JSON can be converted into a provider-neutral target registry.
- Donor audit JSONL entries can inspire an import/export shape, but new audit
  events should follow `audit-event.schema.json`.

## Migration Candidates By Priority

| Priority | Candidate | Classification | Blockers |
| --- | --- | --- | --- |
| 1 | Policy mode presets and deny-by-default tests | preserve | Need Maturity 1 policy modules. |
| 2 | Capability registry from donor known capabilities | redesign | Need schema-backed registry and family/risk metadata. |
| 3 | Audit redaction tests | preserve | Need Maturity 2 audit model. |
| 4 | Safe mock provider states for observe/power/media/boot/input | preserve | Need expanded Maturity 3 mock provider. |
| 5 | MCP tool parity map | preserve | Need Maturity 4 MCP scaffold. |
| 6 | PiKVM observe-only provider slice | defer | Requires Maturity 6 readiness gates. |
| 7 | Redfish observe-only provider slice | defer | Requires Maturity 6 readiness gates. |
| 8 | IPMI/Supermicro provider specs | defer | Requires first real provider lessons. |
| 9 | Supermicro iKVM bridge | defer | Needs separate runtime/container threat model. |

## Provider Readiness Notes

The canonical repo now has PiKVM and Redfish observe-only specs, fake transport
client contracts, fixture-backed observe adapters, disabled config placeholders,
CLI/MCP fixture integration tests, and manual smoke docs.

This does not migrate donor implementation code. Donor provider behavior remains
reference material only, and future live providers must still pass the
constitution, readiness gates, manual smoke review, and mock-only CI
requirements.

## Open Questions

- Should provider routing/fallback be represented as policy, provider registry
  preference, or operator-selected target capability?
- Which donor MCP tool names should remain as compatibility aliases once the new
  MCP interface exists?
- What exact capability ids should represent Redfish event subscription and
  external webhook behavior?
- How should AgenticKVM distinguish read-only account inventory from account or
  credential mutation?
- What audit retention, tamper-evidence, and export formats are required before
  public beta?
- What is the minimum provider conformance suite before PiKVM and Redfish can be
  implemented safely?
