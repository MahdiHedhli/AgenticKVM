# PiKVM Live Hardware Validation

This runbook is for supervised, staged validation against a real PiKVM and a
sacrificial target. It is not a CI procedure and it is not autonomous. Every
stage is one operator-run command plus a human checkpoint before the next stage.

## Preconditions

Before any live actuation, the operator must confirm these items in writing in
the handoff and in the preconditions JSON consumed by the harness:

- Sacrificial target: a reimageable machine doing no real work and containing
  nothing of value.
- Isolated segment: the PiKVM and target are on a network segment with no path
  to systems the operator values.
- Scoped credentials: credentials are for this one PiKVM only, supplied as
  references such as `env:AGENTICKVM_PIKVM_VALIDATION_CREDENTIAL` or a keychain
  reference. Raw secrets must not be committed, logged, or pasted into results.
- Trusted firmware: record the PiKVM firmware version before testing.
- Human presence: the operator is physically or remotely present and advances
  each stage deliberately.

Create a preconditions template:

```bash
python3 scripts/pikvm-live-validation.py preconditions-template \
  --output /tmp/agentickvm-pikvm-preconditions.json
```

Edit the file with real, non-secret facts. Do not put a password, token, host
inventory dump, screenshot, or audit database in the repository.

## Harness Rules

- The harness runs one stage per invocation.
- The harness never chains stages automatically.
- Checkpoint files are written to explicit paths only.
- Every generated checkpoint starts with `operator_confirmed: false`.
- To advance, the operator must review the stage, set `operator_confirmed` to
  `true` in the previous checkpoint, and run the next stage command.
- Stage 2 through Stage 4 are manual execution checkpoints until the real
  authenticated PiKVM HTTP client and real ACT proof verifier are available.
- MSD/ISO mount validation is out of scope for this run.

## Stage 1: Certificate Pinning Preflight

Goal: prove credentials do not go over the wire on a certificate mismatch.

Read-only command:

```bash
python3 scripts/pikvm-live-validation.py stage1-preflight \
  --preconditions /tmp/agentickvm-pikvm-preconditions.json \
  --base-url https://PIKVM-VALIDATION-HOST.example.invalid \
  --credential-ref env:AGENTICKVM_PIKVM_VALIDATION_CREDENTIAL \
  --cert-fingerprint SHA256_CERT_FINGERPRINT \
  --no-verify-ssl \
  --output /tmp/agentickvm-pikvm-stage1.json
```

Expected results:

- The harness captures the real peer certificate fingerprint using an
  unauthenticated TLS connection.
- The matching pin path builds an authenticated client wrapper with the pinned
  certificate as the trust root.
- A deliberately wrong pin aborts before the credential reference is passed to
  the authenticated client factory.
- `verify_ssl=false` without a fingerprint pin is rejected.

Operator checkpoint: confirm Stage 1 behaved correctly before Stage 2.

## Stage 2: Observe

Goal: validate read-only real PiKVM observation.

Manual observations:

- Capture a real screenshot or MJPEG snapshot.
- Read real ATX power state.
- Read real device information.
- Confirm captured screen text is redacted by default in results and audit.

Checkpoint command after the operator has marked Stage 1 confirmed:

```bash
python3 scripts/pikvm-live-validation.py stage2-observe \
  --preconditions /tmp/agentickvm-pikvm-preconditions.json \
  --previous-checkpoint /tmp/agentickvm-pikvm-stage1.json \
  --output /tmp/agentickvm-pikvm-stage2.json
```

Operator checkpoint: confirm observe works and redaction holds before Stage 3.

## Mouse Calibration

Goal: verify screenshot coordinates map to PiKVM absolute HID coordinates before
any click actuation.

Manual observations:

- Pick a known visible point on the real display.
- Use the screenshot-coordinate mapping from
  `agentickvm.providers.pikvm_calibration.PiKVMScreenshotCalibration`.
- Confirm the absolute coordinate corresponds to the intended point.
- Do not click during calibration.

Checkpoint command after Stage 2 is confirmed:

```bash
python3 scripts/pikvm-live-validation.py calibration \
  --preconditions /tmp/agentickvm-pikvm-preconditions.json \
  --previous-checkpoint /tmp/agentickvm-pikvm-stage2.json \
  --output /tmp/agentickvm-pikvm-calibration.json
```

## Stage 3: Lowest-Risk HID Actuation

Goal: prove low-consequence HID actuation is blocked by clearance until the
operator advances it.

Manual observations:

- Use one lowest-consequence HID action, such as one mouse move or one benign
  keystroke into a safe field.
- Confirm the request returns `clearance_required` without clearance.
- Use the mock-cleared path because real ACT transport is not published yet.
- Confirm the action executes once and the same clearance cannot drive a second
  action.
- Confirm HID typed text is redacted in the real audit record.

Checkpoint command after Stage 2 is confirmed:

```bash
python3 scripts/pikvm-live-validation.py stage3-lowest-risk-actuation \
  --preconditions /tmp/agentickvm-pikvm-preconditions.json \
  --previous-checkpoint /tmp/agentickvm-pikvm-stage2.json \
  --output /tmp/agentickvm-pikvm-stage3.json
```

Operator checkpoint: confirm before Stage 4.

## Stage 4: Power Actuation

Goal: prove a single real power action is clearance-gated and target-bound.

Manual observations:

- Choose the least destructive available power action for the sacrificial target.
- Confirm the target physically responds as expected.
- Confirm a clearance issued for this target/action cannot drive a different
  target or action.
- Confirm audit records are redacted and retained.

Checkpoint command after Stage 3 is confirmed:

```bash
python3 scripts/pikvm-live-validation.py stage4-power-actuation \
  --preconditions /tmp/agentickvm-pikvm-preconditions.json \
  --previous-checkpoint /tmp/agentickvm-pikvm-stage3.json \
  --output /tmp/agentickvm-pikvm-stage4.json
```

## Discrepancy Log

Record every mismatch as:

```text
Mock assumed:
Hardware does:
Impact:
Fix or follow-up:
```

Expected likely findings include timing differences, real certificate formatting
quirks, screenshot/MJPEG shape differences, and HID coordinate edge cases.

## Handoff Fields

Final handoff must include:

- Preconditions confirmed: sacrificial target, isolated segment, scoped
  credential reference, firmware version.
- Stage 1 result, including wrong-pin abort-before-credentials.
- Stage 2 observe and real-content redaction result.
- Stage 3 lowest-risk actuation, one-time consumption, and audit redaction.
- Stage 4 power actuation, physical response, and target binding.
- Mouse calibration result.
- All `Mock assumed / Hardware does` discrepancies.
- Confirmation no non-sacrificial machine was touched, no credentials were
  logged, and CI stayed mock-only.
