"""One-shot Qoder SDK adapter used by Recording Agent Hub.

The personal access token is intentionally read by the Qoder SDK from the
environment. This module never stores or logs it.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional

from .runner_common import load_prompt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run a recording task through Qoder Agent SDK")
    result.add_argument("--prompt-file", type=Path, required=True)
    result.add_argument("--workspace", type=Path, required=True)
    result.add_argument("--agent-workspace", type=Path, required=True)
    result.add_argument("--source", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--model", default="efficient")
    return result


def to_json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    elif hasattr(value, "__dict__"):
        value = value.__dict__
    return json.dumps(value, ensure_ascii=False, default=str)


async def run(args: argparse.Namespace) -> int:
    try:
        from qoder_agent_sdk import QoderAgentOptions, access_token_from_env, query
    except ImportError:
        print("Qoder SDK is missing. Run `uv add qoder-agent-sdk` in Recording Agent Hub.")
        return 2
    if not os.environ.get("QODER_PERSONAL_ACCESS_TOKEN"):
        print("Qoder authentication is missing. Set QODER_PERSONAL_ACCESS_TOKEN in the service environment.")
        return 3

    prompt = load_prompt(args)
    options = QoderAgentOptions(
        auth=access_token_from_env(),
        cwd=str(args.agent_workspace),
        add_dirs=[str(args.workspace), str(args.source.parent), str(args.output.parent)],
        model=args.model,
        tools=["Read", "Grep", "Glob", "Bash", "Write", "Edit"],
        allowed_tools=["Read", "Grep", "Glob", "Bash", "Write", "Edit"],
        permission_mode="acceptEdits",
    )
    failed = False
    try:
        async for message in query(prompt=prompt, options=options):
            print(to_json(message), flush=True)
            message_type = getattr(message, "type", None)
            if message_type == "result" and getattr(message, "is_error", False):
                failed = True
    except Exception as exc:
        print(f"Qoder SDK failed: {exc}", flush=True)
        return 1
    return 1 if failed else 0


def main(argv: Optional[list[str]] = None) -> int:
    args = parser().parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
