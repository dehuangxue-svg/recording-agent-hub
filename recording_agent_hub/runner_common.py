"""Shared task envelope for dedicated CLI-agent launchers."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def parser(description: str) -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=description)
    result.add_argument("--prompt-file", type=Path, required=True)
    result.add_argument("--workspace", type=Path, required=True)
    result.add_argument("--agent-workspace", type=Path, required=True)
    result.add_argument("--source", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def load_prompt(args: argparse.Namespace) -> str:
    prompt = args.prompt_file.read_text(encoding="utf-8")
    return prompt + (
        "\n\n## Execution constraints\n\n"
        f"Agent project workspace: `{args.agent_workspace}`\n"
        f"Work files: `{args.workspace}`\n"
        f"Source media: `{args.source}`\n"
        f"Delivery folder: `{args.output}`\n"
        "Do not alter or delete source media. Write reports and logs in the work files folder. "
        "Create delivery files only under the delivery folder.\n"
    )


def run(command: list[str], agent_workspace: Path) -> int:
    try:
        return subprocess.run(command, cwd=str(agent_workspace), check=False, start_new_session=False).returncode
    except FileNotFoundError as exc:
        print(f"Agent CLI is not installed or not on PATH: {exc}")
        return 127


def parent(path: Path) -> str:
    return str(path.expanduser().resolve().parent)


def local_cli(name: str) -> str:
    """Finder-launched macOS apps do not inherit the user's shell PATH."""
    found = shutil.which(name)
    if found:
        return found
    candidates = (
        Path.home() / ".local" / "bin" / name,
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return name


def main_args(description: str, argv: Optional[list[str]] = None) -> argparse.Namespace:
    return parser(description).parse_args(argv)
