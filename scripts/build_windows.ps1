$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Version = uv run python -c "from recording_agent_hub import __version__; print(__version__)"
$AppExe = Join-Path $ProjectRoot "dist\RecordingAgentHub.exe"
$PortableZip = Join-Path $ProjectRoot "dist\Recording-Agent-Hub-Windows-x64-Portable.zip"
$InstallerExe = Join-Path $ProjectRoot "dist\Recording-Agent-Hub-Windows-x64-Setup.exe"

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

uv run --extra qoder --with pyinstaller pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "RecordingAgentHub" `
  --hidden-import watchdog.events `
  --hidden-import watchdog.observers `
  --hidden-import recording_agent_hub.claude_runner `
  --hidden-import recording_agent_hub.codex_runner `
  --hidden-import recording_agent_hub.kimi_runner `
  --hidden-import recording_agent_hub.qoder_runner `
  --hidden-import recording_agent_hub.qoder_cn_runner `
  --hidden-import recording_agent_hub.streamcap_hook `
  --collect-all qoder_agent_sdk `
  recording_agent_hub/desktop.py

Compress-Archive -Path $AppExe -DestinationPath $PortableZip

$IsccCommand = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
$IsccPath = if ($IsccCommand) { $IsccCommand.Source } else { $null }
if (-not $IsccPath) {
  $DefaultIscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
  if (Test-Path $DefaultIscc) { $IsccPath = $DefaultIscc }
}
if ($IsccPath) {
  & $IsccPath "/DMyAppVersion=$Version" "installer\windows\RecordingAgentHub.iss"
} else {
  Write-Warning "Inno Setup was not found. Portable ZIP was created, but the installer was skipped."
}

Write-Host "Created Recording Agent Hub $Version for Windows:"
Write-Host "  $PortableZip"
if (Test-Path $InstallerExe) { Write-Host "  $InstallerExe" }
