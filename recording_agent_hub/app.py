from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shlex
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .runner_common import find_local_cli

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".flv", ".ts", ".m4v"}
APP_DIR = Path.home() / ".recording-agent-hub"
DEFAULT_CONFIG = APP_DIR / "config.json"
MEMORY_DIR = APP_DIR / "memories"
PENDING_HOOK_DIR = APP_DIR / "pending-hooks"
PROJECT_WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_AGENT_WORKSPACE = Path.home() / "Documents"


def bundled_command(module: str) -> List[str]:
    """Run a bundled runner through the app executable, or use normal Python in development."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--runner", module]
    return [sys.executable, "-m", module]


def shell_join(command: List[str]) -> str:
    """Quote a command for the current platform's default command processor."""
    if sys.platform == "win32":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def streamcap_hook_command(server: str = "http://127.0.0.1:8787", profile: str = "default") -> str:
    """Build the post-recording command for the current packaged application."""
    runner = ["--runner", "recording_agent_hub.streamcap_hook", "--server", server, "--profile", profile]
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return shlex.join(["/usr/bin/open", "-n", "-b", "com.recordingagenthub.desktop", "--args", *runner])
        return shell_join([sys.executable, *runner])
    return shell_join([*bundled_command("recording_agent_hub.streamcap_hook"), "--server", server, "--profile", profile])


def process_group_options() -> Dict[str, Any]:
    """Start each agent in a group that can be cancelled with its children."""
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)}
    return {"start_new_session": True}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_config() -> Dict[str, Any]:
    return {
        "ui_language": "zh_CN",
        "data_dir": str(APP_DIR / "data"),
        "agents": {
            "dry-run": {"enabled": True, "command": [sys.executable, "-c", "print('dry run:', open(r'{prompt_file}').read())"]},
            "codex": {
                "enabled": False,
                "command": bundled_command("recording_agent_hub.codex_runner") + ["--prompt-file", "{prompt_file}", "--workspace", "{workspace}", "--agent-workspace", "{agent_workspace}", "--source", "{source}", "--output", "{output}"],
                "notes": "Requires a logged-in Codex CLI. Uses `codex exec` with workspace-write sandboxing.",
            },
            "claude-code": {
                "enabled": False,
                "command": bundled_command("recording_agent_hub.claude_runner") + ["--prompt-file", "{prompt_file}", "--workspace", "{workspace}", "--agent-workspace", "{agent_workspace}", "--source", "{source}", "--output", "{output}"],
                "notes": "Requires a logged-in Claude Code CLI or ANTHROPIC_API_KEY. Uses print mode with structured JSONL output.",
            },
            "hermes": {
                "enabled": False,
                "command": ["hermes", "-Q", "-q", "Read {prompt_file} and complete the task. Write a concise result to {workspace}/agent-result.md.", "--source", "recording-agent-hub"],
            },
            "qoder": {
                "enabled": False,
                "command": bundled_command("recording_agent_hub.qoder_runner") + ["--prompt-file", "{prompt_file}", "--workspace", "{workspace}", "--agent-workspace", "{agent_workspace}", "--source", "{source}", "--output", "{output}"],
                "notes": "Requires Python 3.10+, `uv sync --extra qoder`, and QODER_PERSONAL_ACCESS_TOKEN in the service environment.",
            },
            "qoder-cn": {
                "enabled": False,
                "command": bundled_command("recording_agent_hub.qoder_cn_runner") + ["--prompt-file", "{prompt_file}", "--workspace", "{workspace}", "--agent-workspace", "{agent_workspace}", "--source", "{source}", "--output", "{output}"],
                "notes": "Requires Qoder CN CLI (`qoderclicn`) and QODERCN_PERSONAL_ACCESS_TOKEN for unattended automation.",
            },
            "kimi": {
                "enabled": False,
                "command": bundled_command("recording_agent_hub.kimi_runner") + ["--prompt-file", "{prompt_file}", "--workspace", "{workspace}", "--agent-workspace", "{agent_workspace}", "--source", "{source}", "--output", "{output}"],
                "notes": "Requires a logged-in Kimi Code CLI. Uses `kimi --prompt` in its non-interactive auto permission mode.",
            },
        },
        "profiles": {
            "default": {
                "agent": "dry-run",
                "agent_workspace": str(DEFAULT_AGENT_WORKSPACE),
                "output_template": "{source_parent}/{source_stem}_processed",
                "instructions": "Read the completed recording and complete the task using the instructions, rules, scripts, and tools available in the selected agent workspace. Do not overwrite source media.",
                "rule_files": [],
                "output_validation": "video",
            },
        },
    }


def load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config does not exist: {config_path}. Run init first.")
    with config_path.open(encoding="utf-8") as f:
        config = json.load(f)
    defaults = default_config()
    changed = False
    if "default" not in config.get("profiles", {}):
        config.setdefault("profiles", {})["default"] = copy.deepcopy(defaults["profiles"]["default"])
        changed = True
    for legacy_profile in ("jewelry-roughcut", "generic-review"):
        if legacy_profile in config.get("profiles", {}):
            del config["profiles"][legacy_profile]
            changed = True
    for section in ("agents", "profiles"):
        config.setdefault(section, {})
        for name, value in defaults[section].items():
            if name not in config[section]:
                config[section][name] = copy.deepcopy(value)
                changed = True
            elif isinstance(value, dict):
                for key, default_value in value.items():
                    if key not in config[section][name]:
                        config[section][name][key] = copy.deepcopy(default_value)
                        changed = True
            if section == "agents" and name in {"codex", "claude-code", "qoder", "qoder-cn", "kimi"}:
                command = config[section][name].get("command", [])
                needs_bundled_command = getattr(sys, "frozen", False) and (not command or command[0] != sys.executable)
                if "--agent-workspace" not in command or (name == "codex" and "--ask-for-approval" in command) or needs_bundled_command:
                    config[section][name]["command"] = copy.deepcopy(value["command"])
                    changed = True
    if "data_dir" not in config:
        config["data_dir"] = defaults["data_dir"]
        changed = True
    if config.get("ui_language") not in {"zh_CN", "en", "ja", "ko", "es"}:
        config["ui_language"] = defaults["ui_language"]
        changed = True
    if changed:
        write_json(config_path, config)
    return config


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temp, path)


def save_workspace_memory(name: str, agent: str, workspace: Path, enabled: bool) -> Path:
    """Persist a reusable, non-secret Agent/workspace selection for the native app."""
    resolved = workspace.expanduser().resolve()
    fingerprint = hashlib.sha256(f"{agent}\0{resolved}".encode("utf-8")).hexdigest()[:12]
    path = MEMORY_DIR / f"{agent}-{fingerprint}.json"
    write_json(
        path,
        {
            "name": name.strip() or f"{agent} - {resolved.name}",
            "agent": agent,
            "agent_workspace": str(resolved),
            "enabled": enabled,
            "saved_at": utc_now(),
        },
    )
    return path


def list_workspace_memories() -> List[Dict[str, Any]]:
    if not MEMORY_DIR.is_dir():
        return []
    results: List[Dict[str, Any]] = []
    for path in MEMORY_DIR.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            if all(payload.get(key) for key in ("name", "agent", "agent_workspace")):
                payload["path"] = str(path)
                results.append(payload)
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(results, key=lambda item: item.get("saved_at", ""), reverse=True)


def codex_session_workspaces() -> List[Path]:
    """Read the actual project cwd recorded by Codex Desktop sessions."""
    session_roots = [Path.home() / ".codex" / "sessions", Path.home() / ".codex" / "archived_sessions"]
    workspaces: Dict[Path, float] = {}
    for session_root in session_roots:
        if not session_root.is_dir():
            continue
        for session_file in session_root.rglob("*.jsonl"):
            try:
                with session_file.open(encoding="utf-8") as f:
                    for _ in range(8):
                        line = f.readline()
                        if not line:
                            break
                        entry = json.loads(line)
                        payload = entry.get("payload", {})
                        cwd = payload.get("cwd") if entry.get("type") == "session_meta" else None
                        if cwd:
                            candidate = Path(cwd).expanduser()
                            if candidate.is_dir():
                                workspaces[candidate.resolve()] = session_file.stat().st_mtime
                            break
            except (OSError, json.JSONDecodeError):
                continue
    return [path for path, _ in sorted(workspaces.items(), key=lambda item: item[1], reverse=True)]


def discover_workspace_candidates(agent: str, config: Dict[str, Any]) -> List[str]:
    """Find actual workspaces plus one stable agent root, without noisy intermediate parents."""
    home = Path.home()
    agent_roots = {
        "codex": [home / "Documents" / "Codex"],
        "claude-code": [home / "Documents" / "Claude"],
        "qoder": [home / "Documents" / "Qoder"],
        "qoder-cn": [home / "Documents" / "QoderCN"],
        "kimi": [home / "Documents" / "Kimi"],
        "hermes": [home / "Documents"],
    }
    roots = list(agent_roots.get(agent, [home / "Documents"]))
    if agent == "codex":
        roots.extend(codex_session_workspaces())
    for memory in list_workspace_memories():
        if memory.get("agent") == agent:
            roots.append(Path(memory["agent_workspace"]))
    for profile in config.get("profiles", {}).values():
        if profile.get("agent") == agent and profile.get("agent_workspace"):
            roots.append(Path(profile["agent_workspace"]))

    candidates: List[Path] = []
    for root in roots:
        try:
            root = root.expanduser().resolve()
        except OSError:
            continue
        if not root.is_dir():
            continue
        candidates.append(root)

    unique: List[str] = []
    for candidate in candidates:
        value = str(candidate)
        if value not in unique:
            unique.append(value)
    return unique


def probe_video(path: Path) -> Dict[str, Any]:
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video type: {path.suffix}")
    if not path.is_file():
        raise FileNotFoundError(path)
    command = [find_local_cli("ffprobe") or "ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    if result.returncode:
        raise RuntimeError(f"ffprobe rejected {path}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise RuntimeError(f"Video has no usable duration: {path}")
    stat = path.stat()
    return {"duration_seconds": duration, "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def agent_diagnostics() -> Dict[str, Optional[str]]:
    def locate(name: str) -> Optional[str]:
        return find_local_cli(name)

    checks: Dict[str, Optional[str]] = {
        "codex": locate("codex"),
        "claude-code": locate("claude"),
        "kimi": locate("kimi"),
        "qoder": None,
        "qoder-cn": locate("qoderclicn"),
    }
    try:
        import qoder_agent_sdk  # noqa: F401

        checks["qoder"] = sys.executable
    except ImportError:
        pass
    return checks


class JobStore:
    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self._lock = threading.Lock()
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY,
                  source_path TEXT NOT NULL,
                  source_size INTEGER NOT NULL,
                  source_mtime_ns INTEGER NOT NULL,
                  profile TEXT NOT NULL,
                  agent TEXT NOT NULL,
                  output_path TEXT NOT NULL,
                  workspace_path TEXT NOT NULL,
                  agent_workspace TEXT NOT NULL DEFAULT '',
                  manifest_path TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  started_at TEXT,
                  finished_at TEXT,
                  exit_code INTEGER,
                  error TEXT,
                  log_path TEXT NOT NULL,
                  attempt_count INTEGER NOT NULL DEFAULT 0,
                  UNIQUE(source_path, source_size, source_mtime_ns, profile)
                );
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
            if "agent_workspace" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN agent_workspace TEXT NOT NULL DEFAULT ''")
            if "attempt_count" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0")

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.database), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, row: Dict[str, Any]) -> Dict[str, Any]:
        fields = list(row)
        values = [row[field] for field in fields]
        placeholders = ",".join("?" for _ in fields)
        with self._lock, self.connect() as conn:
            try:
                conn.execute(f"INSERT INTO jobs ({','.join(fields)}) VALUES ({placeholders})", values)
            except sqlite3.IntegrityError:
                existing = conn.execute(
                    "SELECT * FROM jobs WHERE source_path=? AND source_size=? AND source_mtime_ns=? AND profile=?",
                    (row["source_path"], row["source_size"], row["source_mtime_ns"], row["profile"]),
                ).fetchone()
                return dict(existing)
        return row

    def find_existing(self, source_path: str, source_size: int, source_mtime_ns: int, profile: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE source_path=? AND source_size=? AND source_mtime_ns=? AND profile=?",
                (source_path, source_size, source_mtime_ns, profile),
            ).fetchone()
            return dict(row) if row else None

    def list(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")]

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def next_queued(self) -> Optional[Dict[str, Any]]:
        with self._lock, self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            attempt = int(row["attempt_count"] or 0) + 1
            log_path = str(Path(row["workspace_path"]) / f"agent-attempt-{attempt}.log")
            conn.execute(
                "UPDATE jobs SET status='running', started_at=?, finished_at=NULL, attempt_count=?, log_path=? WHERE id=?",
                (utc_now(), attempt, log_path, row["id"]),
            )
            result = dict(row)
            result["status"] = "running"
            result["attempt_count"] = attempt
            result["log_path"] = log_path
            return result

    def finish(self, job_id: str, exit_code: int, error: Optional[str], status: Optional[str] = None) -> None:
        status = status or ("completed" if exit_code == 0 else "failed")
        with self._lock, self.connect() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, finished_at=?, exit_code=?, error=? WHERE id=? AND status='running'",
                (status, utc_now(), exit_code, error, job_id),
            )

    def recover_running(self) -> int:
        with self._lock, self.connect() as conn:
            result = conn.execute(
                "UPDATE jobs SET status='queued', started_at=NULL, finished_at=NULL, exit_code=NULL, error='Recovered after an interrupted app session' WHERE status='running'"
            )
            return result.rowcount

    def cancel(self, job_id: str) -> bool:
        with self._lock, self.connect() as conn:
            result = conn.execute(
                "UPDATE jobs SET status='cancelled', finished_at=?, exit_code=130, error='Cancelled by user' WHERE id=? AND status IN ('queued','running')",
                (utc_now(), job_id),
            )
            return result.rowcount == 1

    def retry(self, job_id: str) -> bool:
        with self._lock, self.connect() as conn:
            result = conn.execute(
                "UPDATE jobs SET status='queued', started_at=NULL, finished_at=NULL, exit_code=NULL, error=NULL WHERE id=? AND status IN ('failed','cancelled','interrupted')",
                (job_id,),
            )
            return result.rowcount == 1


def output_snapshot(path: Path) -> Dict[str, List[int]]:
    if not path.exists():
        return {}
    files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
    snapshot: Dict[str, List[int]] = {}
    for item in files:
        try:
            stat = item.stat()
            key = item.name if path.is_file() else str(item.relative_to(path))
            snapshot[key] = [stat.st_size, stat.st_mtime_ns]
        except OSError:
            continue
    return snapshot


def validate_job_output(job: Dict[str, Any], before: Dict[str, List[int]]) -> List[Dict[str, Any]]:
    manifest = json.loads(Path(job["manifest_path"]).read_text(encoding="utf-8"))
    if manifest.get("connection_test") or manifest.get("output_validation") == "none":
        return []
    output = Path(job["output_path"])
    if not output.exists():
        raise RuntimeError(f"Agent exited successfully but the output folder was not created: {output}")
    files = [output] if output.is_file() else [item for item in output.rglob("*") if item.is_file()]
    videos = [item for item in files if item.suffix.lower() in VIDEO_EXTENSIONS]
    changed: List[Path] = []
    for item in videos:
        stat = item.stat()
        key = item.name if output.is_file() else str(item.relative_to(output))
        if before.get(key) != [stat.st_size, stat.st_mtime_ns]:
            changed.append(item)
    if not changed:
        raise RuntimeError("Agent exited successfully but did not create or update any video files")
    results: List[Dict[str, Any]] = []
    for video in changed:
        metadata = probe_video(video)
        results.append({"path": str(video), **metadata})
    write_json(
        Path(job["workspace_path"]) / "result.json",
        {"job_id": job["id"], "validated_at": utc_now(), "output_files": results},
    )
    return results


@dataclass
class Hub:
    config: Dict[str, Any]
    config_path: Path

    def __post_init__(self) -> None:
        self.data_dir = Path(self.config["data_dir"]).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = JobStore(self.data_dir / "jobs.sqlite")
        self.recovered_jobs = self.store.recover_running()
        self._wake = threading.Event()
        self._paused = threading.Event()
        self._stopped = threading.Event()
        self._process_lock = threading.Lock()
        self._active_process: Optional[subprocess.Popen[str]] = None
        self._active_job_id: Optional[str] = None
        self.activation_callback: Optional[Any] = None
        self._worker = threading.Thread(target=self._work, daemon=True, name="recording-agent-worker")
        self._worker.start()

    def save_config(self) -> None:
        write_json(self.config_path, self.config)

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def set_paused(self, paused: bool) -> None:
        if paused:
            self._paused.set()
        else:
            self._paused.clear()
            self._wake.set()

    def shutdown(self) -> None:
        """Stop accepting work and terminate the currently running agent, if any."""
        self._stopped.set()
        self._wake.set()
        if self._active_job_id:
            self.store.cancel(self._active_job_id)
        self._terminate_active()
        self._worker.join(timeout=7)

    def _terminate_active(self) -> None:
        with self._process_lock:
            process = self._active_process
        if not process or process.poll() is not None:
            return
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=7,
                )
            except (OSError, subprocess.TimeoutExpired):
                process.terminate()
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass

    def cancel(self, job_id: str) -> bool:
        cancelled = self.store.cancel(job_id)
        if cancelled and job_id == self._active_job_id:
            self._terminate_active()
        self._wake.set()
        return cancelled

    def submit(self, source: Path, profile_name: str, connection_test: bool = False) -> Dict[str, Any]:
        profile = self.config.get("profiles", {}).get(profile_name)
        if not profile:
            raise ValueError(f"Unknown profile: {profile_name}")
        metadata = probe_video(source)
        resolved_source = str(source.resolve())
        stored_profile = f"{profile_name}-connection-test" if connection_test else profile_name
        if not connection_test:
            existing = self.store.find_existing(
                resolved_source, metadata["size_bytes"], metadata["mtime_ns"], stored_profile
            )
            if existing:
                return existing
        agent_name = profile["agent"]
        agent = self.config.get("agents", {}).get(agent_name)
        if not agent or not agent.get("enabled"):
            raise ValueError(f"Agent is not enabled: {agent_name}")
        agent_workspace = Path(profile.get("agent_workspace", "")).expanduser()
        if not agent_workspace.is_dir():
            raise ValueError(f"Agent workspace does not exist or is not a directory: {agent_workspace}")
        agent_workspace = agent_workspace.resolve()
        instructions = profile.get("instructions", "")
        if connection_test:
            instructions = (
                "This is an integration test, not a media-editing task. Confirm that the supplied source video "
                "and the agent project workspace are accessible. Do not cut, transcode, copy, modify, or delete any "
                "media. Do not create delivery files. Return exactly one short report beginning with TRIGGER_OK and "
                "include the source filename and current project workspace."
            )
        job_id = uuid.uuid4().hex[:12]
        workspace = self.data_dir / "jobs" / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        output = Path(profile["output_template"].format(source_parent=source.parent, source_stem=source.stem))
        manifest_path = workspace / "manifest.json"
        prompt_path = workspace / "prompt.md"
        manifest = {
            "job_id": job_id,
            "created_at": utc_now(),
            "source": str(source.resolve()),
            "source_metadata": metadata,
            "profile": profile_name,
            "agent": agent_name,
            "workspace": str(workspace),
            "agent_workspace": str(agent_workspace),
            "connection_test": connection_test,
            "output": str(output),
            "rule_files": profile.get("rule_files", []),
            "instructions": instructions,
            "output_validation": profile.get("output_validation", "video"),
        }
        write_json(manifest_path, manifest)
        prompt_path.write_text(
            "# Recording automation task\n\n"
            f"Source media: `{manifest['source']}`\n\n"
            f"Output folder: `{manifest['output']}`\n\n"
            f"Agent project workspace: `{manifest['agent_workspace']}`\n\n"
            f"Job manifest: `{manifest_path}`\n\n"
            "## Instructions\n\n"
            f"{manifest['instructions']}\n\n"
            "## Required rule files\n\n"
            + "\n".join(f"- `{item}`" for item in manifest["rule_files"])
            + "\n",
            encoding="utf-8",
        )
        row = {
            "id": job_id,
            "source_path": str(source.resolve()),
            "source_size": metadata["size_bytes"],
            "source_mtime_ns": metadata["mtime_ns"],
            "profile": f"{profile_name}-connection-test-{job_id}" if connection_test else stored_profile,
            "agent": agent_name,
            "output_path": str(output),
            "workspace_path": str(workspace),
            "agent_workspace": str(agent_workspace),
            "manifest_path": str(manifest_path),
            "status": "queued",
            "created_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "error": None,
            "log_path": str(workspace / "agent.log"),
            "attempt_count": 0,
        }
        created = self.store.create(row)
        self._wake.set()
        return created

    def _work(self) -> None:
        while not self._stopped.is_set():
            self._import_pending_hooks()
            if self._paused.is_set():
                self._wake.wait(timeout=0.5)
                self._wake.clear()
                continue
            job = self.store.next_queued()
            if not job:
                self._wake.wait(timeout=2)
                self._wake.clear()
                continue
            try:
                self._run(job)
            except Exception as exc:
                self.store.finish(job["id"], 1, f"Unexpected worker error: {exc}")

    def _import_pending_hooks(self) -> None:
        if not PENDING_HOOK_DIR.is_dir():
            return
        for path in PENDING_HOOK_DIR.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.submit(Path(payload["source"]), payload.get("profile", "default"))
                path.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired):
                continue

    def _run(self, job: Dict[str, Any]) -> None:
        agent = self.config["agents"][job["agent"]]
        profile = self.config.get("profiles", {}).get(job["profile"], {})
        agent_workspace = job.get("agent_workspace") or profile.get("agent_workspace", "")
        values = {
            "prompt_file": str(Path(job["workspace_path"]) / "prompt.md"),
            "manifest_file": job["manifest_path"],
            "workspace": job["workspace_path"],
            "agent_workspace": agent_workspace,
            "source": job["source_path"],
            "output": job["output_path"],
        }
        command = [part.format(**values) for part in agent.get("command", [])]
        if not command:
            self.store.finish(job["id"], 2, f"Agent {job['agent']} has no command configured")
            return
        log = Path(job["log_path"])
        before = output_snapshot(Path(job["output_path"]))
        try:
            with log.open("w", encoding="utf-8") as output:
                output.write("$ " + " ".join(command) + "\n\n")
                output.flush()
                with self._process_lock:
                    self._active_job_id = job["id"]
                    self._active_process = subprocess.Popen(
                        command,
                        cwd=job["workspace_path"],
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        text=True,
                        **process_group_options(),
                    )
                return_code = self._active_process.wait()
                with self._process_lock:
                    self._active_process = None
                    self._active_job_id = None
            if return_code == 0:
                try:
                    validate_job_output(job, before)
                except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
                    self.store.finish(job["id"], 3, f"Output validation failed: {exc}")
                    return
            error = "Stopped by user" if self._stopped.is_set() else None if return_code == 0 else f"Agent exited with code {return_code}"
            self.store.finish(job["id"], return_code, error)
        except OSError as exc:
            self.store.finish(job["id"], 127, str(exc))
        finally:
            with self._process_lock:
                self._active_process = None
                self._active_job_id = None


class EventHandler:
    def __init__(self, hub: Hub, profile: str) -> None:
        self.hub = hub
        self.profile = profile

    def accept(self, path: str) -> None:
        candidate = Path(path)
        if candidate.suffix.lower() not in VIDEO_EXTENSIONS:
            return
        try:
            job = self.hub.submit(candidate, self.profile)
            print(f"queued {job['id']}: {candidate}", flush=True)
        except Exception as exc:
            print(f"ignored {candidate}: {exc}", file=sys.stderr, flush=True)


def watch_directory(hub: Hub, directory: Path, profile: str) -> None:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as exc:
        raise RuntimeError("watchdog is not installed. Run `uv sync` first.") from exc

    receiver = EventHandler(hub, profile)

    class Handler(FileSystemEventHandler):
        def on_moved(self, event: Any) -> None:
            if not event.is_directory:
                receiver.accept(event.dest_path)

    observer = Observer()
    observer.schedule(Handler(), str(directory), recursive=False)
    observer.start()
    print(f"watching move events in {directory} using profile {profile}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


def web_handler(hub: Hub) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self.json({"status": "ok", "paused": hub.paused})
                return
            if parsed.path == "/api/jobs":
                self.json(hub.store.list())
                return
            if parsed.path == "/api/config":
                self.json({"profiles": hub.config.get("profiles", {}), "agents": hub.config.get("agents", {})})
                return
            if parsed.path == "/api/doctor":
                self.json({"available": agent_diagnostics()})
                return
            if parsed.path == "/api/integration/streamcap":
                command = streamcap_hook_command()
                self.json({"command": command})
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024 * 1024:
                self.json({"error": "Request body is too large"}, 413)
                return
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self.json({"error": "Invalid JSON"}, 400)
                return
            try:
                if parsed.path == "/api/ingest":
                    job = hub.submit(Path(payload["source"]).expanduser(), payload["profile"])
                    self.json(job, 201)
                    return
                if parsed.path == "/api/test-trigger":
                    job = hub.submit(Path(payload["source"]).expanduser(), "default", connection_test=True)
                    self.json(job, 201)
                    return
                if parsed.path == "/api/activate":
                    if hub.activation_callback:
                        hub.activation_callback()
                    self.json({"status": "activated"})
                    return
                if parsed.path.startswith("/api/agents/") and parsed.path.endswith("/toggle"):
                    agent_name = parsed.path.split("/")[3]
                    agent = hub.config.get("agents", {}).get(agent_name)
                    if not agent:
                        self.json({"error": "Unknown agent"}, 404)
                        return
                    agent["enabled"] = bool(payload.get("enabled"))
                    hub.save_config()
                    self.json({"name": agent_name, "enabled": agent["enabled"]})
                    return
                if parsed.path.startswith("/api/profiles/") and parsed.path.endswith("/agent"):
                    profile_name = parsed.path.split("/")[3]
                    profile = hub.config.get("profiles", {}).get(profile_name)
                    agent_name = payload.get("agent")
                    if not profile or agent_name not in hub.config.get("agents", {}):
                        self.json({"error": "Unknown profile or agent"}, 404)
                        return
                    profile["agent"] = agent_name
                    hub.save_config()
                    self.json({"name": profile_name, "agent": agent_name})
                    return
                if parsed.path.startswith("/api/profiles/") and parsed.path.endswith("/workspace"):
                    profile_name = parsed.path.split("/")[3]
                    profile = hub.config.get("profiles", {}).get(profile_name)
                    workspace = Path(str(payload.get("workspace", ""))).expanduser()
                    if not profile:
                        self.json({"error": "Unknown profile"}, 404)
                        return
                    if not workspace.is_dir():
                        self.json({"error": "Agent workspace must be an existing directory"}, 400)
                        return
                    profile["agent_workspace"] = str(workspace.resolve())
                    hub.save_config()
                    self.json({"name": profile_name, "agent_workspace": profile["agent_workspace"]})
                    return
                if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/retry"):
                    job_id = parsed.path.split("/")[3]
                    if not hub.store.retry(job_id):
                        self.json({"error": "Job cannot be retried"}, 409)
                        return
                    hub._wake.set()
                    self.json(hub.store.get(job_id))
                    return
                if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/cancel"):
                    job_id = parsed.path.split("/")[3]
                    if not hub.cancel(job_id):
                        self.json({"error": "Job cannot be cancelled"}, 409)
                        return
                    self.json(hub.store.get(job_id))
                    return
                self.json({"error": "Not found"}, 404)
            except Exception as exc:
                self.json({"error": str(exc)}, 400)

    return Handler


def serve(hub: Hub, port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), web_handler(hub))
    print(f"Recording Agent Hub callback API: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Event-driven post-recording agent hub")
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = result.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--data-dir", type=Path)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("source", type=Path)
    ingest.add_argument("--profile", default="default")
    ingest.add_argument("--server", default="http://127.0.0.1:8787")
    watch = sub.add_parser("watch")
    watch.add_argument("directory", type=Path)
    watch.add_argument("--profile", default="default")
    web = sub.add_parser("web")
    web.add_argument("--port", type=int, default=8787)
    sub.add_parser("jobs")
    sub.add_parser("doctor")
    retry = sub.add_parser("retry")
    retry.add_argument("job_id")
    retry.add_argument("--server", default="http://127.0.0.1:8787")
    return result


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "init":
        if args.config.exists():
            print(f"Keeping existing config: {args.config}")
        else:
            config = default_config()
            if args.data_dir:
                config["data_dir"] = str(args.data_dir.expanduser())
            write_json(args.config, config)
            print(f"Created config: {args.config}")
        return 0
    config = load_config(args.config)
    if args.command == "ingest":
        payload = json.dumps({"source": str(args.source.expanduser()), "profile": args.profile}).encode("utf-8")
        request = Request(args.server.rstrip("/") + "/api/ingest", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=15) as response:
                print(response.read().decode("utf-8"))
        except OSError as exc:
            raise SystemExit(f"Recording Agent Hub is not reachable at {args.server}: {exc}")
        return 0
    if args.command == "watch":
        hub = Hub(config, args.config)
        watch_directory(hub, args.directory.expanduser(), args.profile)
        return 0
    if args.command == "web":
        hub = Hub(config, args.config)
        serve(hub, args.port)
        return 0
    if args.command == "jobs":
        store = JobStore(Path(config["data_dir"]).expanduser() / "jobs.sqlite")
        print(json.dumps(store.list(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "doctor":
        print(json.dumps({"agents": agent_diagnostics(), "enabled": {name: item.get("enabled", False) for name, item in config["agents"].items()}}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "retry":
        request = Request(args.server.rstrip("/") + f"/api/jobs/{args.job_id}/retry", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=15) as response:
                print(response.read().decode("utf-8"))
        except OSError as exc:
            raise SystemExit(f"Recording Agent Hub is not reachable at {args.server}: {exc}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
