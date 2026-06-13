# ACT Clearance Response Mirror

Canonical source: Agentic Control Tower. This AgenticKVM file is a client-side
mirror pending alignment with ACT's canonical clearance contract. It is not an AgenticKVM-owned response contract or proof format.

## Mirrored Expected States

- `clearance_required`
- `cleared`
- `denied`
- `expired`
- `invalid`
- `tower_unavailable`
- `verification_failed`

## Proof Handling

ACT owns the clearance proof/signature format. AgenticKVM treats proof
verification as a fail-closed client interface until ACT publishes the canonical
format. Mock proof verification is allowed only in tests.
