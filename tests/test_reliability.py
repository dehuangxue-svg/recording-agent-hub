from __future__ import annotations

import tempfile
import threading
import time
import unittest
import subprocess
import sys
from pathlib import Path
from unittest import mock

from recording_agent_hub import app, streamcap_hook


def job_row(root: Path, job_id: str = "job-1") -> dict[str, object]:
    workspace = root / job_id
    workspace.mkdir()
    return {
        "id": job_id,
        "source_path": str(root / "source.mp4"),
        "source_size": 100,
        "source_mtime_ns": 200,
        "profile": "default",
        "agent": "dry-run",
        "output_path": str(root / "output"),
        "workspace_path": str(workspace),
        "agent_workspace": str(root),
        "manifest_path": str(workspace / "manifest.json"),
        "status": "queued",
        "created_at": app.utc_now(),
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
        "error": None,
        "log_path": str(workspace / "agent.log"),
        "attempt_count": 0,
    }


class FileHandoffTests(unittest.TestCase):
    def test_wait_for_file_resets_stability_when_file_grows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recording.mp4"
            path.write_bytes(b"first")

            def append() -> None:
                time.sleep(0.04)
                with path.open("ab") as output:
                    output.write(b"second")

            thread = threading.Thread(target=append)
            thread.start()
            started = time.monotonic()
            streamcap_hook.wait_for_file(
                path,
                timeout_seconds=1,
                stable_seconds=0.08,
                minimum_age_seconds=0,
                poll_seconds=0.01,
            )
            thread.join()
            self.assertGreaterEqual(time.monotonic() - started, 0.1)

    def test_pending_submission_is_written_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pending_dir = Path(directory)
            with mock.patch.object(streamcap_hook, "PENDING_DIR", pending_dir):
                pending = streamcap_hook.save_pending("http://127.0.0.1:8787", "default", Path("/tmp/video.mp4"))
            self.assertTrue(pending.is_file())
            self.assertFalse(list(pending_dir.glob("*.tmp")))
            self.assertIn('"profile": "default"', pending.read_text(encoding="utf-8"))


class PlatformIntegrationTests(unittest.TestCase):
    def test_windows_packaged_hook_uses_current_executable(self) -> None:
        executable = r"C:\Program Files\Recording Agent Hub\RecordingAgentHub.exe"
        with (
            mock.patch.object(app.sys, "platform", "win32"),
            mock.patch.object(app.sys, "executable", executable),
            mock.patch.object(app.sys, "frozen", True, create=True),
        ):
            command = app.streamcap_hook_command()
        self.assertIn(f'"{executable}"', command)
        self.assertIn("--runner recording_agent_hub.streamcap_hook", command)
        self.assertNotIn("/usr/bin/open", command)

    def test_windows_agents_start_in_a_new_process_group(self) -> None:
        with mock.patch.object(app.sys, "platform", "win32"):
            options = app.process_group_options()
        self.assertEqual(
            options,
            {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)},
        )

    def test_posix_agents_start_in_a_new_session(self) -> None:
        platform = "darwin" if sys.platform == "win32" else sys.platform
        with mock.patch.object(app.sys, "platform", platform):
            self.assertEqual(app.process_group_options(), {"start_new_session": True})


class JobStoreTests(unittest.TestCase):
    def test_interrupted_job_is_requeued_with_new_attempt_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = app.JobStore(root / "jobs.sqlite")
            store.create(job_row(root))
            first = store.next_queued()
            self.assertEqual(first["attempt_count"], 1)
            self.assertEqual(store.recover_running(), 1)
            second = store.next_queued()
            self.assertEqual(second["attempt_count"], 2)
            self.assertTrue(str(second["log_path"]).endswith("agent-attempt-2.log"))

    def test_cancelled_job_cannot_be_overwritten_by_finish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = app.JobStore(root / "jobs.sqlite")
            store.create(job_row(root))
            running = store.next_queued()
            self.assertTrue(store.cancel(str(running["id"])))
            store.finish(str(running["id"]), 0, None)
            self.assertEqual(store.get(str(running["id"]))["status"], "cancelled")


class OutputValidationTests(unittest.TestCase):
    def test_new_video_output_is_validated_and_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = job_row(root)
            output = Path(str(row["output_path"]))
            output.mkdir()
            video = output / "1.mp4"
            video.write_bytes(b"video")
            app.write_json(Path(str(row["manifest_path"])), {"connection_test": False, "output_validation": "video"})
            with mock.patch.object(app, "probe_video", return_value={"duration_seconds": 3.0, "size_bytes": 5, "mtime_ns": 1}):
                result = app.validate_job_output(row, {})
            self.assertEqual([item["path"] for item in result], [str(video)])
            self.assertTrue((Path(str(row["workspace_path"])) / "result.json").is_file())

    def test_unchanged_old_output_does_not_count_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = job_row(root)
            output = Path(str(row["output_path"]))
            output.mkdir()
            video = output / "1.mp4"
            video.write_bytes(b"old")
            app.write_json(Path(str(row["manifest_path"])), {"connection_test": False, "output_validation": "video"})
            with self.assertRaisesRegex(RuntimeError, "did not create or update"):
                app.validate_job_output(row, app.output_snapshot(output))


if __name__ == "__main__":
    unittest.main()
