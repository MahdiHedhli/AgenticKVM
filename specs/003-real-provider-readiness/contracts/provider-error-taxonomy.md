# Provider Error Taxonomy

Provider errors must normalize into safe provider results before they reach CLI,
MCP, audit, or future SDK adapters.

| Error | Category | Retryable | Safe To Show | Audit Severity | Stop Behavior | Approval Could Resolve |
| --- | --- | --- | --- | --- | --- | --- |
| `ProviderDisabledError` | config | no | yes | medium | stop action | no |
| `ProviderNotFoundError` | config | no | yes | medium | stop action | no |
| `TargetNotFoundError` | config | no | yes | medium | stop action | no |
| `UnsupportedCapabilityError` | provider | no | yes | medium | stop action | no |
| `ProviderTimeoutError` | network | yes | yes | medium | retry allowed | no |
| `ProviderTLSVerificationError` | network | no | yes | high | stop action | no |
| `ProviderAuthenticationRequiredError` | credential | no | no | high | stop action | yes |
| `ProviderAuthenticationFailedError` | credential | no | no | high | stop action | yes |
| `ProviderAuthorizationError` | credential | no | no | high | stop action | yes |
| `ProviderConnectionError` | network | yes | yes | medium | retry allowed | no |
| `ProviderProtocolError` | protocol | no | yes | medium | stop action | no |
| `ProviderResponseValidationError` | protocol | no | yes | medium | stop action | no |
| `ProviderRateLimitedError` | provider | yes | yes | medium | retry allowed | no |
| `ProviderUnsafeOperationError` | safety | no | yes | critical | stop session | no |
| `ProviderMutationBlockedError` | safety | no | yes | critical | stop action | no |
| `ProviderSecretRequiredError` | credential | no | no | high | stop action | yes |
| `ProviderConfigError` | config | no | yes | medium | stop action | no |

Sensitive details must be redacted. Credential errors must never reveal raw
credentials, tokens, passwords, or secret references.
