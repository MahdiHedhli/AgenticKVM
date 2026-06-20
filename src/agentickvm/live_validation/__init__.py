"""Manual live-hardware validation helpers.

Nothing in this package is used by CI to contact real devices. The helpers are
for operator-run validation scripts with explicit human checkpoints.
"""

from agentickvm.live_validation.pikvm import (
    PiKVMLiveValidationError,
    RealTLSPiKVMProbe,
    StageCheckpoint,
    ValidationPreconditions,
    build_stage_checkpoint,
    deliberately_wrong_fingerprint,
    load_preconditions,
    run_stage1_cert_preflight,
    validate_prior_checkpoint,
)

__all__ = [
    "PiKVMLiveValidationError",
    "RealTLSPiKVMProbe",
    "StageCheckpoint",
    "ValidationPreconditions",
    "build_stage_checkpoint",
    "deliberately_wrong_fingerprint",
    "load_preconditions",
    "run_stage1_cert_preflight",
    "validate_prior_checkpoint",
]
