# PiKVM Screenshot Artifact Policy

## Purpose

This contract defines how PiKVM screenshot and screen artifacts are handled in
AgenticKVM before any live PiKVM screenshot transport exists.

## Sensitivity

Screenshots may expose secrets, host state, machine identity, installation
flows, customer data, and operator activity. They are sensitive artifacts by
default.

## Current Implementation

AgenticKVM currently supports metadata-only fake screenshot observations. It
does not capture live screenshots, write live screenshot artifacts, upload
artifacts, or resolve credentials.

## Required Behavior

- Tests use synthetic fixtures or metadata-only screenshot records.
- Screenshot artifact roots must be explicit.
- Artifact roots must not default into tracked repo paths.
- Artifact names must not include target ids or provider ids.
- Audit records screenshot metadata only.
- Raw bytes are redacted before audit, CLI, MCP, SDK, logs, or docs output.
- Live screenshots require explicit scope and manual smoke approval.
- CI must never write live screenshots or contact PiKVM targets.

## Metadata Fields

Screenshot metadata may include:

- `kind`
- `sensitivity`
- `artifact_root`
- `artifact_name`
- `content_type`
- `byte_length`
- `provider_id`
- redacted `target_id`
- `raw_bytes_included: false`

## Prohibited Fields

Screenshot metadata and audit records must not include:

- raw image bytes
- `raw_image`
- `image_bytes`
- `screenshot_bytes`
- credentials
- cookies
- bearer values
- raw target hostnames
- raw target IP addresses

## Future Live Smoke

Future live PiKVM screenshot smoke must configure:

- artifact output path outside the repo
- audit path outside the repo
- credential reference outside the repo
- timeout and TLS policy
- cleanup plan
- stop conditions

Live screenshot smoke must not run in CI.
