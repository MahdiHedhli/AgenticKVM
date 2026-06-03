# Quickstart: Control Plane Bootstrap

This quickstart describes the bootstrap repository behavior. It does not control
real hardware.

## Install For Local Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m pip install pytest
```

## Run Tests

```bash
PYTHONPATH=src python3 -m pytest
```

Expected result: unit, contract, and security tests pass using only the mock
provider and offline files.

## Inspect Policy Examples

```bash
ls examples/policies
```

Use the examples to compare how Observe, Assisted, Supervised, Full Control, and
Custom policies express the same capability families with different decisions.

## Current Provider Behavior

The only provider scaffolded in bootstrap is `MockProvider`. It does not contact
real hardware. It records the requested action and returns a safe mock result.

## Next Implementation Slice

The next slice should implement a policy loader and default-deny capability
resolution before adding any real provider.
