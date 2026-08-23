"""Dedicated Claude Code print-mode adapter."""
from __future__ import annotations

from typing import Optional

from .runner_common import load_prompt, local_cli, main_args, parent, run


def main(argv: Optional[list[str]] = None) -> int:
    args = main_args("Run a recording task through Claude Code", argv)
    command = [
        local_cli("claude"),
        "--print", load_prompt(args),
        "--output-format", "stream-json",
        "--verbose",
        "--max-turns", "50",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read,Grep,Glob,Bash,Write,Edit",
        "--add-dir", str(args.workspace),
        "--add-dir", parent(args.source),
        "--add-dir", parent(args.output),
    ]
    return run(command, args.agent_workspace)


if __name__ == "__main__":
    raise SystemExit(main())
