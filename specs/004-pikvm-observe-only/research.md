# Research: PiKVM Observe-Only Provider

## Provider Lessons

The donor spike showed that PiKVM can expose useful out-of-band observations
such as screenshots, streamer state, HID state, MSD state, and ATX state. The
canonical project separates observation from input, media, and power actions so
read-only work can mature first.

## Screenshot Sensitivity

Screen content can contain secrets, recovery tokens, hostnames, customer data,
or operator-only context. Screenshot and screen text outputs must be treated as
sensitive observations and routed through audit redaction rules.

## Network And TLS

Live PiKVM support must define timeouts and TLS verification behavior before
network code is added. Certificate pinning from the donor spike is a useful
lesson, but the future implementation must be specified and tested separately.

## Deferred Questions

- Should `observe.screen` and `observe.screenshot` be distinct capabilities or
  aliases at the interface layer?
- Should screenshot output be stored as an audit artifact, summarized only, or
  returned directly with explicit operator policy?
- Which PiKVM status fields are safe to expose by default?
