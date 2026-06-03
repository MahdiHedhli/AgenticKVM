# Quickstart: PiKVM Observe-Only Provider

This quickstart is for local fixture-backed tests only.

## Run Offline Tests

```text
uv run --with pytest --python python3.13 python -m pytest
```

## Use The Placeholder Config

The placeholder config documents the future shape but remains disabled by
default. It is not a live PiKVM config and contains no credentials.

```text
examples/config/pikvm-observe-placeholder.yaml
```

## Future Live Smoke

Live PiKVM smoke testing is deferred until the readiness gates are satisfied and
an operator explicitly approves an isolated lab target. CI must never run live
PiKVM tests.
