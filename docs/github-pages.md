# GitHub Pages Site Plan

## Purpose

Create a straightforward public site for AgenticKVM that explains the product,
architecture, safety model, provider taxonomy, and roadmap without implying
that live providers or a live MCP server are production-ready.

Primary message:

> Give your AI agent hands for real machines, with safety guardrails built in.

## Audience

- infrastructure operators evaluating AI-assisted recovery workflows
- security reviewers checking authority boundaries and audit behavior
- developers who may build providers, MCP adapters, or mock-first tests
- future contributors who need a high-level product map before reading specs

## Positioning

AgenticKVM is a policy-controlled infrastructure control plane for AI-assisted
machine observation, recovery, and operation across KVM, BMC, and future
remote-session providers.

The site should emphasize:

- out-of-band first design
- policy-controlled actions
- approval gates
- target and provider registries
- audit trail
- mock-first development
- MCP-ready integration
- future provider readiness without overclaiming live support

## Site Structure

The first site is a single static page under `site/` with sections for:

- Home
- Why AgenticKVM
- How it works
- Safety guardrails
- Provider roadmap
- MCP and agents
- Getting started
- Roadmap

This avoids adding a heavy frontend stack, generator, package manager,
analytics, remote fonts, or build-time dependencies.

## Claims Allowed

- designed for safe agentic control
- mock-first
- provider-ready
- observe-only readiness
- dependency-free mock-only MCP adapter and host compatibility layer
- future provider families
- live MCP server gated
- live providers deferred
- real providers disabled by default
- CI is mock-only

## Claims Disallowed

- production ready
- fully supports live PiKVM, Redfish, RDP, VNC, RustDesk, or MeshCentral today
- autonomous recovery without human approval
- secure by default without qualification
- zero risk
- hands-off production operation
- live MCP server is implemented

## Safety Language

Use clear language from the constitution:

- policy is the authority boundary
- unknown capabilities fail closed
- tools cannot call providers directly
- providers and targets must be registered
- `approval_required` is a first-class outcome
- Full Control does not bypass audit, scope, emergency stop, or invariants
- secrets are redacted by default
- audit is mandatory

## Deployment Plan

This branch adds static files under `site/` and documents GitHub Pages setup.
It does not add a GitHub Actions workflow yet.

Reason: the repository currently has no `.github/workflows/` convention. A
future workflow should be added only after human review confirms the repository
should publish GitHub Pages from `main`.

Safe setup options after review:

1. Configure GitHub Pages in repository settings to serve from a static branch
   or folder if that matches repository policy.
2. Add a minimal workflow that uploads `site/` using official GitHub Pages
   actions with:
   - `contents: read`
   - `pages: write`
   - `id-token: write`
   - no secrets
   - no provider tests
   - no live infrastructure access

## Open Questions

- What public GitHub repository URL should the footer use once published?
- Should GitHub Pages be enabled manually in repository settings, or should a
  reviewed workflow publish `site/`?
- Should the site eventually link to generated API/reference docs?
- Should the site remain one page or split into multiple static pages later?
