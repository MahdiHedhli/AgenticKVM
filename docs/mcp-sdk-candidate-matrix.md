# MCP SDK Candidate Matrix

## Status

Docs-only review artifact. No MCP SDK dependency has been selected, added, or
installed.

## Evidence Rule

Candidate facts must come from primary sources: official SDK lists,
repositories, package registries, specifications, security guidance, and
release metadata. Unknown fields stay `TODO`; unknown safety-critical fields
hold the candidate.

## Candidate Summary

| Candidate | Status | Reason |
| --- | --- | --- |
| Dependency-free internal host layer | hold | Current safe baseline; not a live MCP SDK. Keeps conformance tests stable while dependency review proceeds. |
| Official Python MCP SDK, package `mcp` | candidate for offline trial | Official Python SDK with verified package metadata and MCP transport support, but not selected until acceptance gates and conformance proof pass. |
| Other third-party Python MCP frameworks | hold | No primary-source review completed. Must not be selected from hearsay or stale assumptions. |

## Detailed Matrix

| Field | Dependency-free internal host layer | Official Python MCP SDK, `mcp` | Other third-party Python MCP frameworks |
| --- | --- | --- | --- |
| Package/project name | AgenticKVM internal `agentickvm.mcp_sdk` | `mcp` | TODO |
| Source/repository | Local repo only | https://github.com/modelcontextprotocol/python-sdk | TODO |
| Package registry | Not packaged separately | https://pypi.org/project/mcp/ | TODO |
| License | AgenticKVM project license | PyPI lists MIT License; repository exposes MIT license metadata | TODO |
| Language/runtime | Python, dependency-free | Python; PyPI lists Python `>=3.10` and Python 3.10-3.13 classifiers | TODO |
| Transport modes | No live transport; in-memory compatibility only | Official docs and package description list stdio, SSE, and Streamable HTTP support | TODO |
| Stdio support | Not a server | MCP transport spec defines stdio; Python SDK docs show stdio client examples | TODO |
| Local-only mode | Yes, in-process only | Likely possible through stdio or in-memory test helpers, but AgenticKVM adapter proof is required | TODO |
| Server/listener behavior | No listener exists | HTTP/Streamable HTTP server examples can expose listeners; acceptance gate must require no listener by default | TODO |
| Dependency footprint | No runtime SDK dependency | TODO: inspect wheel metadata and lockfile impact in trial branch | TODO |
| Maturity | Current project scaffold | Official MCP docs list Python SDK as Tier 1; PyPI classifier lists Development Status: Beta | TODO |
| Maintenance signal | Maintained in this repo | Official repo and PyPI release metadata show active release artifacts; exact cadence requires release-history review | TODO |
| Packaging risk | Low while internal | Conditional: transitive dependencies, extras, lockfile impact, and optional transports must be reviewed before adoption | TODO |
| Security concerns | Must keep tests honest and avoid becoming a fake authority boundary | HTTP transport exposure, local server compromise, token passthrough, SSRF, and session risks must be constrained by AgenticKVM gates | TODO |
| Fit for AgenticKVM | Baseline for host conformance and mock-only testing | Promising candidate for an offline trial because it is the official Python SDK, but it must adapt to the host compatibility contract | Unknown |
| Missing information | Future real SDK behavior | dependency tree, import-time side effects, default logging, exact server startup behavior, auth hooks, mock-only adapter proof | all fields |
| Status | hold as baseline | candidate for offline trial, not selected | hold |
| Notes | Keep until a real SDK-backed adapter passes all conformance tests | Do not add dependency in this lane. Trial must be branch-scoped, mock-only, and acceptance-gated. | Reject any package without primary-source evidence. |

## Official Python SDK Facts Verified

- The MCP SDK index lists Python as an official Tier 1 SDK.
- The official Python SDK repository describes the SDK as a Python
  implementation for MCP servers and clients.
- PyPI currently lists package `mcp` version `1.27.2`, released May 29, 2026,
  with Python `>=3.10`, MIT license metadata, and Python 3.10 through 3.13
  classifiers.
- MCP transport specification defines stdio and Streamable HTTP as standard
  transport mechanisms.
- The Python SDK testing documentation describes an in-memory connected
  server/client session helper, which may be useful for future mock-only tests.

## Security Notes From MCP Guidance

Future review must account for:

- local MCP server compromise risk
- Streamable HTTP DNS rebinding and listener exposure risk
- token passthrough as a forbidden pattern
- SSRF risks in OAuth or metadata discovery flows
- session hijacking and session impersonation risks
- per-client consent and authorization boundaries

AgenticKVM-specific consequence: a live MCP server can never be trusted as the
authority boundary. It must remain an interface adapter over policy,
registries, approval, and audit.

## Decision

No dependency is selected.

The official Python SDK is the only reviewed candidate currently eligible for
a future offline trial. It remains blocked on:

- live MCP server boundary ADR acceptance
- live server acceptance gate completion
- packaging and supply-chain review
- dependency tree inspection
- mock-only adapter proof
- full host conformance test pass through an SDK-backed adapter
- audit-store checkpoint/export/failure behavior preservation
