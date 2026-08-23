# Contributing

Thanks for improving Recording Agent Hub.

## Before opening a pull request

1. Keep changes focused. Do not mix adapter, UI, and unrelated refactors in one pull request.
2. Never commit a token, local config, task log, source recording, or generated application/installer.
3. Run the tests:

   ```bash
   uv run python -m unittest discover -s tests -v
   ```

4. If you change the desktop app, build it on the platform you changed:

```bash
./scripts/build_macos_app.sh
```

```powershell
.\scripts\build_windows.ps1
```

## Agent adapters

Adapters must use argument arrays, never an interpolated shell command. Limit agent access to the job workspace, selected agent workspace, source parent, and delivery parent. Do not log credentials.

## Documentation

Update `README.md` and `docs/USER_GUIDE_zh-CN.md` whenever a user-facing workflow or setup requirement changes.
