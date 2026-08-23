"""Submit a StreamCap recording after its built-in completion hook fires."""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

PENDING_DIR = Path.home() / ".recording-agent-hub" / "pending-hooks"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Send a completed StreamCap recording to Recording Agent Hub")
    result.add_argument("--server", default="http://127.0.0.1:8787")
    result.add_argument("--profile", default="default")
    result.add_argument("--record_name")
    result.add_argument("--save_file_path", required=True)
    result.add_argument("--save_type")
    result.add_argument("--split_video_by_time")
    result.add_argument("--converts_to_mp4", default="False")
    return result


def final_path(args: argparse.Namespace) -> Path:
    source = Path(args.save_file_path)
    if str(args.converts_to_mp4).lower() == "true" and source.suffix.lower() == ".ts":
        return source.with_suffix(".mp4")
    return source


def wait_for_file(
    path: Path,
    timeout_seconds: int = 3600,
    stable_seconds: float = 15,
    minimum_age_seconds: float = 10,
    poll_seconds: float = 1,
) -> None:
    """Wait for a non-empty recording to remain unchanged before handing it off."""
    deadline = time.monotonic() + timeout_seconds
    last_signature: tuple[int, int] | None = None
    stable_since: float | None = None
    while time.monotonic() < deadline:
        try:
            stat = path.stat()
        except OSError:
            stat = None
        if stat and path.is_file() and stat.st_size > 0:
            signature = (stat.st_size, stat.st_mtime_ns)
            if signature == last_signature:
                stable_since = stable_since or time.monotonic()
                stable_for = time.monotonic() - stable_since
                old_enough = time.time() - stat.st_mtime >= minimum_age_seconds
                if stable_for >= stable_seconds and old_enough:
                    return
            else:
                last_signature = signature
                stable_since = time.monotonic()
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for final recording: {path}")


def save_pending(server: str, profile: str, source: Path) -> Path:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    path = PENDING_DIR / f"{uuid.uuid4().hex}.json"
    temp = path.with_suffix(".json.tmp")
    payload = {
        "server": server,
        "profile": profile,
        "source": str(source),
        "created_at": time.time(),
    }
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return path


def submit(server: str, profile: str, source: Path) -> None:
    payload = json.dumps({"source": str(source), "profile": profile}).encode("utf-8")
    request = Request(server.rstrip("/") + "/api/ingest", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:
        print(response.read().decode("utf-8"), flush=True)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    source = final_path(args)
    try:
        wait_for_file(source)
        source = source.resolve()
        pending = save_pending(args.server, args.profile, source)
        last_error: Exception | None = None
        for delay in (0, 2, 5, 10, 20):
            if delay:
                time.sleep(delay)
            try:
                submit(args.server, args.profile, source)
                pending.unlink(missing_ok=True)
                return 0
            except (OSError, URLError) as exc:
                last_error = exc
        raise URLError(f"submission queued for retry: {last_error}")
    except (OSError, TimeoutError, URLError) as exc:
        print(f"Recording Agent Hub hook failed: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
