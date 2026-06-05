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

## Local Preview

Open `site/index.html` in a browser, or serve the directory with any local
static file server.

## GitHub Pages

The current branch does not add a GitHub Actions workflow. See
`docs/github-pages.md` for setup options and safety constraints.

If a workflow is added later, it should publish only the static `site/`
directory, require no secrets, and never run live provider or hardware tests.
