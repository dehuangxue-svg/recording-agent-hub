# Recording Agent Hub User Guide

Recording Agent Hub is a local macOS application that hands a completed recording to a selected AI coding agent and that agent's project workspace. It does not contain industry-specific rules. Prompts, scripts, skills, `AGENTS.md`, and delivery rules belong to the project workspace you select.

## 1. Install

1. Download the DMG or ZIP for your Mac from GitHub Releases.
2. Move `Recording Agent Hub.app` to Applications.
3. Open the app. On first launch, macOS may require Finder -> right-click the app -> Open.
4. Keep the app running while StreamCap is expected to send completed recordings.

The app does not bundle Codex, Claude Code, Qoder, Kimi, their CLIs, accounts, or tokens. Install and authenticate the agent you want to use on each Mac separately.

## 2. Understand the two workspaces

### Agent project workspace

This is where the agent starts. Select the project directory that contains your workflow instructions, scripts, rules, skills, and tools. For example, select the project that owns your rough-cut rules for a rough-cut workflow.

### Job workspace

The app creates a separate internal directory for every recording. It contains the manifest, prompt, and task logs. Its default location is:

```text
~/.recording-agent-hub/data/jobs/
```

You do not select the job workspace manually.

## 3. Configure an agent and workspace

1. Open **Automation Settings**.
2. Choose an agent.
3. Click **Auto Discover**.
4. Choose a real project workspace from the list, or click **Choose Folder**.
5. Enable the agent.
6. Click **Save Settings**.

Saving settings creates a reusable **workspace memory** automatically. You never need to import a JSON file: select a memory on the **Workspace Memories** tab and click **Use Selected Memory** to restore its agent, workspace, and enabled state.

### Auto discovery

- **Codex:** reads the real `cwd` values from locally stored Codex session records and shows the Codex project root plus actual workspaces.
- **Other agents:** shows common project roots, saved workspace memories, and the currently configured workspace.
- Discovery only offers candidate paths. It does not alter project files.

## 4. Connect StreamCap

1. Copy the command under **Connect StreamCap** in the app.
2. In StreamCap, enable **Execute custom script after recording**.
3. Paste the command into StreamCap's custom script command field.
4. Keep Recording Agent Hub running.

The packaged command identifies the app by bundle identifier, not an absolute user path. The same command works after switching agents on the same Mac and can be used on another Mac with the same app installed. The active workspace memory on that Mac determines which agent and project run.

The callback waits for a final file that is unchanged for 15 seconds before submission. If the app is temporarily unavailable, the callback is saved to a local pending outbox and retried when the app starts again.

## 5. Run a connection test first

1. Open the **Test** tab.
2. Choose a sample video.
3. Click **Test Trigger**.
4. Check its status on the **Jobs** tab.

The test only checks that the agent can access the sample video and project workspace. It must not cut, transcode, copy, delete, or deliver media. A successful report begins with `TRIGGER_OK`.

## 6. Run, pause, stop, and cancel

- **Pause Automation:** keeps the app running but does not claim new queued work.
- **Resume Automation:** resumes queued work.
- **Cancel Task:** cancels the selected task and requests termination of its active agent process when applicable.
- **Stop and Quit:** stops the local callback service and terminates the active agent. StreamCap recordings will not be submitted until the app is opened again.

## 7. Agent prerequisites

| Agent | Local requirement | Recommended authentication |
| --- | --- | --- |
| Codex | Install and log in to `codex` CLI | Codex CLI login |
| Claude Code | Install and log in to `claude` CLI | Claude Code login or `ANTHROPIC_API_KEY` |
| Qoder | Install Qoder Agent SDK | `QODER_PERSONAL_ACCESS_TOKEN` supplied outside app config |
| Qoder CN | Install and log in to `qoderclicn` | Qoder CN CLI login or `QODERCN_PERSONAL_ACCESS_TOKEN` |
| Kimi Code | Install and log in to `kimi` CLI | Kimi Code CLI login |
| Hermes | Install `hermes` CLI | Hermes authentication flow |

Do not paste tokens into the app, GitHub issues, commits, prompts, or chat. Use each agent's login flow, macOS Keychain, launchd environment, or a secrets manager.

## 8. Troubleshooting

### Port 8787 is already in use

Another Recording Agent Hub instance or an old development server is still running. Quit the older instance, then reopen the app. You normally do not need to change the StreamCap command.

### An agent shows "CLI/SDK not found"

Install and authenticate the required CLI on that Mac, then restart the app or refresh Agent Status. Finder-launched apps do not inherit a terminal's temporary `PATH`; the app also checks `~/.local/bin`.

### A completed recording does not create a task

Confirm that the app is running, the StreamCap callback is enabled, the selected agent is enabled, and the selected workspace still exists. Pending callbacks are stored at:

```text
~/.recording-agent-hub/pending-hooks/
```

### An agent succeeds but no output video is accepted

By default, a job needs a newly created or updated video in the configured output directory that passes `ffprobe` validation. Inspect the selected agent workspace's rules, scripts, task prompt, and task log to verify that the agent knows the delivery requirement.

## 9. Local data and cleanup

All local state lives at:

```text
~/.recording-agent-hub/
```

It contains settings, workspace memories, the jobs database, logs, and pending callbacks. Source recordings remain at their original paths and are not moved or deleted. Quit the app before cleanup; removing this entire directory deletes workspace memories and job history.
