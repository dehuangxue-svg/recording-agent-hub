"""Dedicated non-interactive Codex CLI adapter."""
from __future__ import annotations

from typing import Optional

from .runner_common import load_prompt, local_cli, main_args, parent, run


def main(argv: Optional[list[str]] = None) -> int:
    args = main_args("Run a recording task through Codex CLI", argv)
    result_file = args.workspace / "agent-result.md"
    command = [
        local_cli("codex"), "exec",
        "--json",
        "--approve-for-me",
        "--cd", str(args.agent_workspace),
        "--add-dir", str(args.workspace),
        "--add-dir", parent(args.source),
        "--add-dir", parent(args.output),
        "--skip-git-repo-check",
        "--output-last-message", str(result_file),
        load_prompt(args),
    ]
    return run(command, args.agent_workspace)


if __name__ == "__main__":
    raise SystemExit(main())
