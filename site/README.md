# AgenticKVM Site

This directory contains a static GitHub Pages-ready site for AgenticKVM.

The site is intentionally simple:

- `index.html`
- `styles.css`
- no JavaScript
- no analytics or tracking
- no remote fonts
- no build step
- no live provider behavior
- no MCP SDK dependency
- public beta copy links to release notes, known limitations, security, and
  roadmap docs

## Local Preview

Open `site/index.html` in a browser, or serve the directory with any local
static file server.

## GitHub Pages

The repository includes a GitHub Pages workflow that publishes only this static
`site/` directory after merge and repository setting enablement. See
`docs/github-pages.md` and `docs/github-pages-enablement-checklist.md` for
setup steps and safety constraints.
