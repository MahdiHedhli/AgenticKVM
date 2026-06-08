import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_lint_sanity_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/lint-sanity.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["checked"]["python_files"] > 0
    assert payload["checked"]["text_files"] > 0
    assert payload["checked"]["metadata"]["sdk_trial_dependency_present"] is False
    assert (
        payload["checked"]["generated_local_artifacts"]["committed_generated_artifacts"]
        == 0
    )
    assert "mcp==1.27.2" not in result.stdout.lower()


def test_no_generated_local_release_artifacts_are_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = result.stdout.splitlines()
    forbidden_suffixes = (".sqlite", ".sqlite3", ".db", ".png", ".jpg", ".jpeg", ".webp")
    for path in tracked:
        if path.startswith("tests/fixtures/"):
            continue
        lowered = path.lower()
        assert not lowered.endswith(forbidden_suffixes)
        if lowered.endswith(".json"):
            assert "release-manifest" not in lowered
            assert "audit-export" not in lowered
            assert "audit-checkpoint" not in lowered
            assert "approval-queue" not in lowered
            assert "approval_queue" not in lowered


def test_lint_sanity_script_is_dependency_free() -> None:
    source = (ROOT / "scripts" / "lint-sanity.py").read_text(encoding="utf-8")

    assert "requests" not in source
    assert "socket" not in source
    assert "subprocess" not in source
    assert "import ast" in source
    assert "import json" in source
