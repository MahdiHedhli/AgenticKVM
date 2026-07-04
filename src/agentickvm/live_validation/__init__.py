"""Manual live-hardware validation helpers.

Nothing in this package is used by CI to contact real devices. The helpers are
for operator-run validation scripts with explicit human checkpoints.
"""

from agentickvm.live_validation.http_mutate import (
    PinnedMutatingHTTPSJSONClient,
)
from agentickvm.live_validation.http_read import (
    GETOnlyHTTPSJSONClient,
    resolve_credential_pair,
)
from agentickvm.live_validation.pikvm import (
    PiKVMLiveValidationError,
    RealPiKVMAuthenticatedHTTPClient,
    RealTLSPiKVMProbe,
    StageCheckpoint,
    ValidationPreconditions,
    build_stage_checkpoint,
    deliberately_wrong_fingerprint,
    load_preconditions,
    pikvm_http_client_factory,
    run_stage1_cert_preflight,
    validate_prior_checkpoint,
)
from agentickvm.live_validation.pikvm_mutate import (
    RealPiKVMHTTPMutationClient,
    build_live_pikvm_mutation_transport,
    pikvm_mutating_http_client_factory,
)
from agentickvm.live_validation.redfish import (
    RealRedfishHTTPReadClient,
    RealTLSRedfishProbe,
    RedfishLiveValidationError,
    build_live_redfish_read_transport,
    collect_redfish_read_evidence,
    redfish_http_client_factory,
)
from agentickvm.live_validation.redfish_mutate import (
    RealRedfishHTTPMutationClient,
    build_live_redfish_mutation_transport,
    redfish_mutating_http_client_factory,
)

__all__ = [
    "GETOnlyHTTPSJSONClient",
    "PiKVMLiveValidationError",
    "PinnedMutatingHTTPSJSONClient",
    "RealPiKVMAuthenticatedHTTPClient",
    "RealPiKVMHTTPMutationClient",
    "RealRedfishHTTPMutationClient",
    "RealRedfishHTTPReadClient",
    "RealTLSPiKVMProbe",
    "RealTLSRedfishProbe",
    "RedfishLiveValidationError",
    "StageCheckpoint",
    "ValidationPreconditions",
    "build_live_pikvm_mutation_transport",
    "build_live_redfish_mutation_transport",
    "build_live_redfish_read_transport",
    "build_stage_checkpoint",
    "collect_redfish_read_evidence",
    "deliberately_wrong_fingerprint",
    "load_preconditions",
    "pikvm_http_client_factory",
    "pikvm_mutating_http_client_factory",
    "redfish_http_client_factory",
    "redfish_mutating_http_client_factory",
    "resolve_credential_pair",
    "run_stage1_cert_preflight",
    "validate_prior_checkpoint",
]
