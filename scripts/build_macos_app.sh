#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
cd "$ROOT"
VERSION="$(uv run python -c 'from recording_agent_hub import __version__; print(__version__)')"
ARCH="$(uname -m)"
APP="dist/Recording Agent Hub.app"
ZIP="dist/Recording-Agent-Hub-macOS.zip"
DMG="dist/Recording-Agent-Hub-macOS-${ARCH}.dmg"

rm -rf build dist
uv run --with pyinstaller pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Recording Agent Hub" \
  --osx-bundle-identifier "com.recordingagenthub.desktop" \
  --hidden-import watchdog.events \
  --hidden-import watchdog.observers \
  --hidden-import recording_agent_hub.claude_runner \
  --hidden-import recording_agent_hub.codex_runner \
  --hidden-import recording_agent_hub.kimi_runner \
  --hidden-import recording_agent_hub.qoder_runner \
  --hidden-import recording_agent_hub.qoder_cn_runner \
  --hidden-import recording_agent_hub.streamcap_hook \
  recording_agent_hub/desktop.py

/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$APP/Contents/Info.plist"
if /usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$APP/Contents/Info.plist" >/dev/null 2>&1; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$APP/Contents/Info.plist"
else
  /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$APP/Contents/Info.plist"
fi
xattr -cr "$APP"

if [[ -n "${CODESIGN_IDENTITY:-}" ]]; then
  codesign --force --deep --options runtime --timestamp --sign "$CODESIGN_IDENTITY" "$APP"
else
  codesign --force --deep --sign - "$APP"
fi

COPYFILE_DISABLE=1 ditto -c -k --norsrc --keepParent "$APP" "$ZIP"
hdiutil create -volname "Recording Agent Hub" -srcfolder "$APP" -ov -format UDZO "$DMG"

if [[ -n "${CODESIGN_IDENTITY:-}" ]]; then
  codesign --force --timestamp --sign "$CODESIGN_IDENTITY" "$DMG"
fi
if [[ -n "${NOTARY_PROFILE:-}" ]]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$APP"
  xcrun stapler staple "$DMG"
fi

echo "Created version $VERSION ($ARCH):"
echo "  $ROOT/$APP"
echo "  $ROOT/$ZIP"
echo "  $ROOT/$DMG"
