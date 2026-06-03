# Quickstart

This quickstart verifies readiness scaffolding without touching real hardware.

## Run Mock-Only Tests

```text
uv run --with pytest --python python3.13 python -m pytest
```

## Inspect Mock Config

```text
agentickvm list-providers
agentickvm list-targets
agentickvm call --target mock-host --tool get_power_state
```

## Confirm Deferred Live Work

Before any live provider smoke test:

1. create a provider-specific observe-only spec
2. document manual smoke steps
3. use secret references only
4. keep CI mock-only
5. require explicit human approval

No live command is provided by this spec.
