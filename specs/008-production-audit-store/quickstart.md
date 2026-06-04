# Quickstart: Local Audit Verification

This quickstart is mock-only and uses temporary or explicitly supplied local
paths. It does not configure a production backend.

```python
from agentickvm.control_plane import LocalJSONLAuditSink
from agentickvm.control_plane.audit_checkpoint import create_audit_checkpoint
from agentickvm.control_plane.audit_export import export_audit_log, verify_audit_export

audit_path = "/tmp/agentickvm-audit/events.jsonl"
sink = LocalJSONLAuditSink(audit_path)

# Emit audit events through normal ControlPlane flows.

checkpoint = create_audit_checkpoint(audit_path, audit_log_id="local-demo")
bundle = export_audit_log(audit_path, checkpoint=checkpoint)
result = verify_audit_export(bundle)
assert result.ok
```

Tests must use `tmp_path` and must not write audit logs to global paths.
