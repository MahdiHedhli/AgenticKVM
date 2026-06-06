# Site Preview

AgenticKVM's public site is a static GitHub Pages-ready page under `site/`.

## Command

```bash
python scripts/check-site.py
```

The script validates:

- `site/index.html` exists
- `site/styles.css` exists
- mobile viewport metadata exists
- local anchors resolve
- local links resolve
- no script tags are present
- no analytics or tracking strings are present
- no remote fonts are referenced
- no forbidden live-support overclaims are present
- provider roadmap language stays conservative
- Pages workflow publishes only `site/`
- Pages workflow does not use secrets, dependency install, or tests

## Scope

The preview check is static. It does not start a web server, open a browser,
deploy Pages, call external URLs, or require network access.

## Deployment Boundary

The Pages workflow uploads the `site/` directory only. Repository settings still
need human confirmation after merge.

The site must not include:

- analytics
- tracking pixels
- remote fonts
- external scripts
- live provider endpoints
- credentials
- SDK trial dependency claims
- claims that deferred providers are implemented today

## Future Work

Future site work may add multi-page static docs or generated reference pages,
but any generator or build dependency requires a separate review.
