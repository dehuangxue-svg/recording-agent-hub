"""Dedicated Kimi Code CLI non-interactive adapter."""
from __future__ import annotations

from typing import Optional

from .runner_common import load_prompt, local_cli, main_args, parent, run


def main(argv: Optional[list[str]] = None) -> int:
    args = main_args("Run a recording task through Kimi Code", argv)
    command = [
        local_cli("kimi"),
        "--prompt", load_prompt(args),
        "--output-format", "stream-json",
        "--add-dir", str(args.workspace),
        "--add-dir", parent(args.source),
        "--add-dir", parent(args.output),
    ]
    return run(command, args.agent_workspace)


if __name__ == "__main__":
    raise SystemExit(main())
