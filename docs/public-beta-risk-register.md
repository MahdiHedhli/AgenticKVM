# Public Beta Risk Register

This register tracks release-facing risks for the AgenticKVM public beta branch
stack. It is not a production approval. Human review is still required before
merge, release, or any live provider use.

| Risk | Impact | Mitigation | Current Status | Owner / Decision | Release Blocker |
| --- | --- | --- | --- | --- | --- |
| Live provider credentials | Credential material could be mishandled if future live providers resolve secrets too early. | Credential references are parsed but not resolved in automated tests; preflight requires `credential_ref` evidence without revealing it. | Open for future live-provider phase. | Operator/security review must select credential backend. | Yes for live provider use; no for mock-only beta. |
| SQLite audit integrity | Local audit DB corruption or tampering could weaken investigation evidence. | SQLite hash-chain verification, checkpoint/export helpers, explicit-path tests, and hardening docs. | Hardened for local beta; production backend still deferred. | Human review of audit backend limitations. | No for mock-only beta; yes for production claim. |
| Approval transport UX | File-backed approvals are usable but not a polished operator workflow. | CLI approval queue, redacted previews, scope/fingerprint checks, denial/expiry audit events. | Local transport ready for beta review. | Operator UX review. | No for beta if docs note limitations. |
| Artifact retention | Screenshot/screen artifacts can be sensitive if persisted in unsafe paths. | Artifact policy rejects repo paths in tests; preflight requires explicit artifact path for PiKVM. | Metadata-only automated flows covered. | Human retention policy decision. | Yes for live screenshot use. |
| Python MCP SDK adoption | Trial dependency may expand attack surface or logging exposure. | SDK trial remains on separate branch; mainline adoption deferred. | Held outside this branch. | Human dependency/security review. | No for beta unless MCP SDK is adopted. |
| Public docs overclaims | Website or README could imply unsupported live providers. | Site/docs safety tests reject known overclaim phrases; roadmap labels live providers as gated/deferred. | Guarded by release checks. | Maintainer copy review. | Yes. |
| Real hardware safety | Future smoke tests could affect physical systems. | Live smoke is manual-only; CI/test mode blocks preflight; no live providers enabled by default. | No hardware touched. | Operator approval required before lab smoke. | Yes for live use. |
| Provider mutation risk | Power, media, firmware, BIOS, storage, network, and account actions could be dangerous. | Hard invariants, provider preflight observe-only checks, playbook gating, approval requirements. | Mutating live provider actions not implemented. | Security review before any mutation phase. | Yes. |
| Remote-session scope creep | RustDesk, VNC, RDP, and MeshCentral may be mistaken for out-of-band control. | Provider taxonomy labels them future in-band remote-session providers with different availability assumptions. | Roadmap-only. | Product/security review. | No for beta if docs remain clear. |
| Package/release immaturity | Build tooling, lock strategy, coverage thresholds, and release artifacts are not fully productionized. | Release-quality scripts, deferred build gate docs, package checks, release manifest, PR review package. | Beta candidate, not production-ready. | Maintainer release decision. | No for beta if limitations are published. |
| Unsupported platform assumptions | Tests currently target the local Python/uv workflow; platform-specific behavior may appear later. | Development/testing docs and CI workflows define expected mock-only path. | Needs CI confirmation after PR. | Maintainer CI review. | No for local branch; yes before public release if CI fails. |

## Current Recommendation

The branch can be reviewed as a mock-first public beta candidate. It should not
be marketed as production-ready, and it must not be used for unattended live
provider operations.
