# Artifact Safety

AgenticKVM treats screenshots and screen observations as sensitive artifacts.
They can contain passwords, recovery keys, hostnames, IP addresses, customer
data, boot prompts, installer screens, and console sessions.

Future remote desktop streams, session thumbnails, clipboard captures, and
screen recordings are also sensitive artifacts.

## Current State

The repository implements metadata-only screenshot artifact safety checks. It
does not implement live screenshot capture, live PiKVM transport, credential
resolution, or artifact upload.

Tests use synthetic fixtures and temporary directories only.

## Rules

- Screenshot artifacts must be explicitly scoped.
- Artifact output must not default into tracked repository paths.
- Tests must use temporary directories.
- Audit records metadata only, never raw screenshot bytes.
- Artifact names must not include target ids or provider ids.
- Screenshot metadata must carry a sensitivity label.
- Raw screenshot bytes must be redacted from audit and external output.
- Live screenshots remain blocked until the manual smoke gate is approved.
- Future remote desktop stream artifacts remain blocked until an in-band
  provider spec defines consent, retention, redaction, and audit behavior.

## Paths

Future live smoke config must provide an explicit artifact output path outside
the repository. Committed examples use placeholders only.

Common local artifact directories and screenshot filename patterns are ignored
by `.gitignore`.

## Audit

Audit may record:

- artifact kind
- sensitivity label
- content type
- byte length
- redacted target id
- artifact name
- artifact root

Audit must not record:

- raw image bytes
- raw screen contents
- raw stream contents
- clipboard contents
- credentials
- cookies
- bearer values
- target-sensitive names in artifact names

## Cleanup

Manual smoke operators are responsible for removing local screenshot artifacts
after review while preserving required audit records.
