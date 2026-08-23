# Recording Agent Hub

**A local macOS bridge from completed recordings to an AI coding agent and its selected project workspace.**

Recording Agent Hub is designed for event-driven post-recording automation. A recorder such as StreamCap calls the app only after a recording finishes; the app validates the finished file, creates a durable task, and runs the selected agent in the selected project workspace.

It is independent from StreamCap's source code and release cycle. It does not contain domain rules: your agent workspace owns the prompts, scripts, skills, `AGENTS.md`, and delivery rules.

## User manual

English manual: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)  
Chinese manual: [docs/USER_GUIDE_zh-CN.md](docs/USER_GUIDE_zh-CN.md)

The manual covers installation, Agent workspaces, saved workspace memories, StreamCap setup, tests, pause/stop, agent prerequisites, and troubleshooting.

## What it does

- Native macOS desktop application. The local HTTP endpoint exists only for recorder callbacks; users do not operate a browser dashboard.
- StreamCap completion hook, not scheduled directory polling.
- Durable SQLite queue, per-attempt logs, retries, cancellation, interrupted-job recovery, and output validation.
- Saved workspace memories: choose a saved Agent/workspace combination in the app with one click.
- Workspace discovery. Codex candidates are read from locally recorded Codex session `cwd` values; other agents use saved workspaces and common project roots.
- Built-in adapters for Codex CLI, Claude Code, Qoder, Qoder CN CLI, Kimi Code, and Hermes.
- Local-first. Source recordings stay in place; task metadata and logs stay under `~/.recording-agent-hub/`.

## Quick start

### Use a release build

1. Download the DMG or ZIP for your Mac from GitHub Releases.
2. Move `Recording Agent Hub.app` to Applications and open it.
3. In **Automation Settings**, select an agent and its project workspace, enable it, then save.
4. Copy the StreamCap completion command from the app into StreamCap's custom script setting.
5. Run a connection test before enabling a real recording workflow.

Each Mac must have the selected agent's CLI installed and authenticated. The app does not bundle agent accounts or credentials.

### Run from source

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/OWNER/recording-agent-hub.git
cd recording-agent-hub
uv sync
uv run recording-agent-hub init
uv run recording-agent-hub-desktop
```

## StreamCap integration

In the app, copy the command under **Connect StreamCap**. In StreamCap, enable its "execute custom script after recording" option and paste the command.

The packaged command uses the app bundle identifier rather than an absolute user path. It is portable between Macs that have the same application installed. Which agent runs is determined by the currently selected workspace memory on that Mac.

The hook waits for a stable final file, writes an unsent callback to a local outbox before submission, and retries automatically after the app restarts.

## Agent requirements

| Agent | Interface | Requirement |
| --- | --- | --- |
| Codex | `codex exec` | Install and log in to Codex CLI |
| Claude Code | `claude --print` | Install and log in, or configure `ANTHROPIC_API_KEY` |
| Qoder | Qoder Agent SDK | Install the optional SDK and provide `QODER_PERSONAL_ACCESS_TOKEN` outside app config |
| Qoder CN | `qoderclicn -p` | Install Qoder CN CLI and authenticate it or supply `QODERCN_PERSONAL_ACCESS_TOKEN` outside app config |
| Kimi Code | `kimi --prompt` | Install and log in to Kimi Code CLI |
| Hermes | `hermes` CLI | Install and authenticate Hermes |

Never paste a token into an issue, commit, app setting, or task prompt. Use the agent's own login flow, Keychain, launchd environment, or a secrets manager.

## Build a macOS app

```bash
./scripts/build_macos_app.sh
```

This creates an `.app`, ZIP, and an architecture-specific DMG under `dist/`. A local build uses ad-hoc signing. For a public Gatekeeper-compatible release, set `CODESIGN_IDENTITY` and `NOTARY_PROFILE` before building.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```

## Security and privacy

See [SECURITY.md](SECURITY.md). The project does not store agent tokens in its config, workspace memories, manifests, or logs. Do not commit `~/.recording-agent-hub/`, generated apps, release archives, recordings, or `.env` files.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
