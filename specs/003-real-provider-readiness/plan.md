# Implementation Plan

## Sequence

1. Harden provider, target, and config contracts.
2. Add disabled real-provider placeholder contracts.
3. Add mock provider contract coverage for observe-only capabilities.
4. Add local audit persistence and redaction checks.
5. Add manual smoke-test documentation requirements.
6. Add provider-specific specs for PiKVM or Redfish observe-only behavior.

## Safety Constraints

- No live provider network calls in this spec.
- No credentials in repo config.
- No real hardware in CI.
- No mutating capabilities in the first real-provider slice.
- All interface calls must route through registries and `ControlPlane`.

## Verification

Run:

```text
uv run --with pytest --python python3.13 python -m pytest
```

Provider-specific smoke tests must be manual, opt-in, and outside CI.
