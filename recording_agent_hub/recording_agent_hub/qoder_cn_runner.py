"""Dedicated Qoder CN CLI adapter for local, headless tasks."""
from __future__ import annotations

from typing import Optional

from .runner_common import load_prompt, local_cli, main_args, parent, run


def main(argv: Optional[list[str]] = None) -> int:
    args = main_args("Run a recording task through Qoder CN CLI", argv)
    command = [
        local_cli("qoderclicn"),
        "-p", load_prompt(args),
        "--output-format", "stream-json",
        "-w", str(args.agent_workspace),
        "--add-dir", str(args.workspace),
        "--add-dir", parent(args.source),
        "--add-dir", parent(args.output),
        "--allowed-tools", "Read,Grep,Glob,Bash,Write,Edit",
        "--max-turns", "50",
    ]
    return run(command, args.agent_workspace)


if __name__ == "__main__":
    raise SystemExit(main())
