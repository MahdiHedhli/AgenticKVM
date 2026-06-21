# AgenticKVM Beta-Candidate Status

## ACT clearance consume seam: CASE A — contract is pinnable (real path wired)

The Agentic Control Tower (ACT) clearance contract is **pinnable today**, so the
consume seam has been wired to the **real ACT path** behind the existing
fail-closed seam and mirror-aligned to the published contract.

Evidence the contract is pinnable (Agentic Control Tower repo):

- Published, versioned schema: `contracts/clearance/clearance.schema.json`
  (`act.clearance.v2`).
- Published proof format: `contracts/clearance/proof-format.md`
  (`ACT-CLEARANCE-PROOF-V1`, Ed25519, fixed signed-field order).
- Committed verification vector: `contracts/clearance/test-vector.json`
  (tower public key + signature).
- Live gateway endpoints: `/v1/hermes/tools/approval_requested` and
  `/v1/hermes/tools/approval_status`.
- A real consumer (the Hermes `act-clearance` plugin) and an
  `extensions.agentickvm` namespace for target/provider/capability context.

### What is wired (real)

- **Real proof verifier** — `control_plane/act_proof.py`:
  `ACTClearanceProofVerifier` verifies the `ACT-CLEARANCE-PROOF-V1` Ed25519 proof
  using a vendored pure-Python RFC 8032 verify (no third-party crypto
  dependency, fully offline). It replaces the fail-closed
  `ACTPendingProofVerifier` through the existing `proof_verifier` seam.
- **Real transport client** — `control_plane/act_http_client.py`:
  `ACTHTTPClearanceClient` maps the mirror request to the published ACT request
  shape, polls the gateway approval endpoints, and parses the `act.clearance.v2`
  response. The HTTP transport is injected; the default `UrllibACTHTTPTransport`
  uses only the standard library.
- **Mirror alignment** — `control_plane/clearance.py`: `ClearanceResponse` now
  carries `contract_version` and the verbatim `bound_material` ACT signed;
  `clearance_response_from_act_payload` maps ACT `state` → mirror status,
  resolves target identity from the core field or `extensions.agentickvm`, and
  preserves `operator_message`, `params_fingerprint`, `short_code`,
  `risk_family`, and `expires_at` on the poll shape. The risk-family enum
  mirrors the eight tower-resolved `act.clearance.v2` families; ACT owns
  risk-family resolution, so the verifier trusts the proof's cryptographic
  binding for tower-resolved families and only enforces string equality for the
  aircraft's coarse `low_risk`/`high_risk` labels.

### Real-clearance coverage (mock-only CI, no live network)

- `tests/security/test_act_clearance_proof.py` verifies the **committed tower
  proof vector** end-to-end and proves every bound field is tamper-evident, plus
  unknown-key / wrong-algorithm / unsupported-version / mismatched-digest
  fail-closed paths.
- `tests/security/test_act_http_clearance.py` drives the **real consume path**
  end-to-end with an injected transport: request mapping → gateway poll →
  `act.clearance.v2` parse → real Ed25519 proof verification → request/response
  binding. Fingerprint and target binding hold; an unavailable gateway and an
  expired clearance fail closed; ACT state→status mapping is covered.

CI exercises no live network. Default deployments remain fail-closed
(`ACTPendingProofVerifier`) until an operator configures the tower public key(s)
and gateway base URL.

### Params-fingerprint parity

ACT computes `params_fingerprint`, `extensions_digest`, and the operator
`short_code` authoritatively from the redacted payload and extensions envelope
the aircraft sends. `control_plane/act_fingerprint.py` mirrors that exact
algorithm (canonical `json.dumps` + SHA-256, per the Tower contract), and the
real client predicts the fingerprint over exactly the payload it puts on the
wire (`predicted_act_params_fingerprint`). Parity is pinned by
`tests/security/test_act_fingerprint_parity.py`. Wiring this predicted
fingerprint into the engine's outbound clearance request (so the binding holds
live) lands with the config/runtime wiring of the real ACT client.

## Outstanding (operator-run, not in CI)

- Live end-to-end clearance against a running ACT gateway to confirm the
  params-fingerprint parity against a real tower computation.
- Supervised live PiKVM validation and read-only BMC validation (hardware is not
  validated; all actuation/transport QA is mock-only).
