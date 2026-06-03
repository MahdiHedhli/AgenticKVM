"""AgenticKVM CLI entry point."""

from __future__ import annotations

from collections.abc import Sequence

from agentickvm.cli.main import main as _main


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    return _main(argv)


__all__ = ["main"]
