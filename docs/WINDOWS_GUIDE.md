# Recording Agent Hub for Windows

This guide covers the Windows build. The workflow model is identical to the macOS build: StreamCap finishes a recording, invokes the local hook, and Recording Agent Hub sends the final file to the selected Agent and project workspace.

## 1. Install

1. Download `Recording-Agent-Hub-Windows-x64-Setup.exe` from GitHub Releases. The portable ZIP is available for computers where installation is not allowed.
2. Run the installer and launch **Recording Agent Hub** from the Start menu.
3. If Windows SmartScreen warns about an unsigned community build, verify that it came from this repository before choosing **More info -> Run anyway**.
4. Keep the app running when StreamCap finishes a recording.

The installer is per-user and does not require administrator access. Local settings, workspace memories, jobs, and logs are stored under:

```text
%USERPROFILE%\.recording-agent-hub\
```

## 2. Install prerequisites

Install FFmpeg and confirm that `ffprobe` works in PowerShell:

```powershell
ffprobe -version
```

Install and authenticate every Agent CLI you intend to use. The packaged app contains the Qoder SDK adapter, but it does not contain accounts or tokens. Restart Recording Agent Hub after installing a CLI so it can refresh Windows executable paths.

Common CLI locations such as `%APPDATA%\npm`, `%LOCALAPPDATA%\Microsoft\WindowsApps`, `%USERPROFILE%\.local\bin`, and Scoop shims are detected automatically.

## 3. Select an Agent workspace

1. Open **Automation Settings**.
2. Select the Agent.
3. Click **Auto Discover**, then choose the actual project workspace containing that Agent's rules and scripts. Use **Choose Folder** when it is not listed.
4. Enable the Agent and click **Save Settings**.

The saved entry appears under **Workspace Memories** and can be selected directly later. No JSON import is required.

## 4. Connect StreamCap

1. Copy the command shown under **Connect StreamCap**.
2. In StreamCap, enable its post-recording custom script option.
3. Paste the command exactly as shown, including quotes around the executable path.

The Windows command points to the current installed executable. Generate it on each computer instead of copying a command from a computer where the app was installed in a different directory.

## 5. Test without editing

On the **Test** tab, choose a sample recording and run **Test Trigger**. The test only asks the Agent to verify access to the source and project workspace. It must not edit, transcode, copy, or deliver media. A successful result begins with `TRIGGER_OK`.

## 6. Pause, cancel, and stop

- **Pause Automation** stops claiming new queued tasks while the app remains available.
- **Cancel Task** cancels the selected task and terminates its Agent process tree.
- **Stop and Quit** stops the callback service and terminates the active Agent process tree.

## 7. Troubleshooting

### The Agent or ffprobe is missing

Confirm the command works in a new PowerShell window, then restart Recording Agent Hub. CLI installation folders that are only present in a temporary terminal `PATH` are not visible to an already-running desktop app.

### Port 8787 is occupied

Close the other Recording Agent Hub instance or old development server, then reopen the app.

### StreamCap does not create a task

Confirm that Recording Agent Hub is running, the post-recording command is enabled, the selected Agent is enabled, and its project workspace still exists. Failed callbacks remain under `%USERPROFILE%\.recording-agent-hub\pending-hooks\` and are retried when the app starts.

### Qoder authentication

Set `QODER_PERSONAL_ACCESS_TOKEN` outside the app configuration, for example through a user environment variable or a credential launcher. Restart the app after changing the environment. Never put a token in an issue, workspace memory, task prompt, or commit.

## 8. Build from source

Install Python 3.10+, `uv`, and optionally Inno Setup 6, then run:

```powershell
uv sync
uv run python -m unittest discover -s tests -v
.\scripts\build_windows.ps1
```

The portable ZIP and installer are written to `dist\`. PyInstaller cannot produce a Windows executable from macOS, so official Windows artifacts are built by the repository's Windows GitHub Actions runner.
