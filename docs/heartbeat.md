# AgenticKVM Heartbeat

Use this recurring prompt every 2 hours for autonomous maintenance work.

## Prompt

You are maintaining the canonical AgenticKVM repository only. Work in the
`AgenticKVM` repo, not `Agentic-KVM` or any other donor spike.

Use specs as the source of truth, in this order:

1. `.specify/memory/constitution.md`
2. `specs/*/spec.md`
3. `specs/*/contracts/*`
4. `docs/*`
5. implementation and tests

Before changing files, inspect `git status`. If there are unrelated dirty
worktree changes, stop and report them. Do not overwrite or revert work you did
not make.

Prefer tests, schemas, mocks, docs, and small reversible slices. Avoid real
hardware by default. Avoid secrets by default. Do not add provider behavior
unless the spec, policy, approval, audit, mock, and tests support it.

Never weaken safety gates. Never bypass policy. Never let tools call providers
directly. Never merge your own pull requests.

Recommended loop:

1. Re-read the relevant spec and constitution section.
2. Select the smallest unfinished task.
3. Add or tighten tests/contracts first where possible.
4. Implement the smallest safe change.
5. Run focused tests.
6. Summarize files changed, tests run, risks, and next task.
