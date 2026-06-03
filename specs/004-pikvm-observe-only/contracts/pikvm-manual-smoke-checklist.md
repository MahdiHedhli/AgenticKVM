# PiKVM Manual Smoke Checklist

Manual smoke is not approved by this spec. It is a future checklist that may be
used only after readiness gates pass and an operator explicitly approves an
isolated lab target.

- Confirm target is an isolated lab machine.
- Confirm provider config is disabled by default before the test.
- Confirm credentials are provided through an approved secret reference, never
  committed config.
- Confirm only observe capabilities are in scope.
- Confirm no keyboard, mouse, power, media, or boot action will run.
- Confirm timeout and TLS verification settings are documented.
- Confirm audit output path is explicit and writable.
- Confirm CI is not running the smoke test.
- Run one observe call at a time.
- Stop on unexpected provider response, timeout, auth failure, certificate
  warning, or any request that would mutate state.
