# GitHub Pages Enablement Checklist

Use this checklist after the public beta branch is reviewed and merged. It does
not require secrets and must not expose provider configs, credentials, audit
artifacts, or live infrastructure.

## Before Enabling

- [ ] `site/index.html` and `site/styles.css` are present.
- [ ] `.github/workflows/pages.yml` exists.
- [ ] `python3 scripts/check-site.py` passes.
- [ ] `python3 scripts/validate-docs.py` passes.
- [ ] Site copy does not claim live provider support.
- [ ] Site copy links to roadmap, security statement, and known limitations.
- [ ] No analytics, tracking, remote fonts, JavaScript, credentials, or provider
      configs are present in `site/`.

## Repository Settings

1. Open GitHub repository settings.
2. Go to Pages.
3. Set source to GitHub Actions.
4. Confirm the workflow is `.github/workflows/pages.yml`.
5. Confirm the workflow uploads only `site/`.
6. Confirm the workflow requires no GitHub Actions secrets.

## Expected Workflow

The Pages workflow should:

- run on push to `main` and `workflow_dispatch`
- use official GitHub Pages actions
- publish static `site/`
- use permissions:
  - `contents: read`
  - `pages: write`
  - `id-token: write`
- install no dependencies
- run no tests
- contact no live providers
- require no secrets

## Post-Enable Validation

After the first deploy:

- [ ] Pages workflow passes.
- [ ] Public URL loads the homepage.
- [ ] Homepage has no console-visible tracking or external assets.
- [ ] Footer links work.
- [ ] Known limitations are discoverable.
- [ ] Security statement is discoverable.
- [ ] Provider roadmap labels live providers as gated/deferred.

## Rollback

If Pages output is wrong:

1. Disable Pages in repository settings or stop deploying from GitHub Actions.
2. Revert the Pages workflow or site changes.
3. Re-run `python3 scripts/check-site.py`.
4. Re-enable Pages only after review.

## Badges And Public URL

Do not add README badges until the public repository URL is confirmed. After the
first successful Pages deploy, a maintainer may update README links and badges
in a separate branch.
