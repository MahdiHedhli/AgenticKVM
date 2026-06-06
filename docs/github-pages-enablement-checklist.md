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

## Step-By-Step Enablement Runbook

Use this runbook only after the public beta branch has been merged to `main` and
CI has passed.

1. In GitHub, open the AgenticKVM repository.
2. Open Settings.
3. Select Pages from the left navigation.
4. Under Build and deployment, set Source to GitHub Actions.
5. Save the setting if GitHub requires a save action.
6. Open Actions.
7. Select the GitHub Pages workflow.
8. Run it manually with `workflow_dispatch`, or wait for the next push to
   `main`.
9. Confirm the workflow uploads `site/` and completes successfully.
10. Open the deployed Pages URL shown by the workflow.
11. Validate the homepage:
    - public beta candidate status is visible
    - known limitations are linked
    - security statement is linked
    - live providers are described as gated or deferred
    - no analytics, tracking, remote fonts, or scripts are present
12. If the public URL is final, update README badges and links in a separate
    reviewed branch.

Do not add secrets, deploy tokens, analytics, provider config, credentials, or
live smoke commands to the Pages workflow.

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

If the site exposes an unsupported claim after deployment, disable Pages first,
then fix the site copy in a normal pull request.

## Badges And Public URL

Do not add README badges until the public repository URL is confirmed. After the
first successful Pages deploy, a maintainer may update README links and badges
in a separate branch.
