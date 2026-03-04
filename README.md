# AirType

Type on your Android phone, text appears on your Windows PC. Uses glide typing on mobile when it's faster than a physical keyboard.

This is a personal project, tested with Gboard. If you run into issues feel free to open an issue and I'll do my best to help.

## How It Works

Your phone connects to your PC over WiFi via WebSocket. As you type on Android (including glide typing, autocorrect, voice input), keystrokes are sent to your PC and typed automatically.

## Quick Start

### Windows

**Option A: Download the exe**
- Download `AirType.exe` from [Releases](../../releases)
- Run it - a system tray icon appears
- Note the IP address and port shown

**Option B: Run from source**
```bash
cd windows
pip install -r requirements.txt
python gui.py       # GUI with system tray
python main.py      # CLI version (lighter, no GUI dependencies)
```

The CLI version supports flags:
```
--debug     Show all messages as they arrive
--silent    Minimal output
--mode      ascii (default) or unicode (clipboard-based)
--port      WebSocket port (default: 8765)
```

### Android

**Option A: Download the APK**
- Download `AirType-release.apk` from [Releases](../../releases)
- Enable "Install from unknown sources" and install it

**Option B: Build from source**
- See [Building](#android-app) below

Then:
- Open AirType on your phone
- Enter your PC's IP and port (shown in the Windows app)
- Tap Connect
- Start typing!

## Building

### Windows Executable

```bash
cd windows
pip install -r requirements.txt
python -m PyInstaller build.spec
```

Output: `windows/dist/AirType.exe`

### Android App

Requires Android Studio or the Android SDK with Java.

```bash
cd android
./gradlew assembleDebug
```

Output: `android/app/build/outputs/apk/debug/AirType-debug.apk`

Install via:
```bash
adb install app/build/outputs/apk/debug/AirType-debug.apk
```

## Requirements

- Windows PC and Android phone on the same WiFi network
- Python 3.10+ (if running from source)
- Android 8.0+ (API 26)

## Troubleshooting

**Can't connect?**
- Ensure both devices are on the same WiFi network
- Check that Windows Firewall allows the connection (the app will prompt)
- The IP address to enter is shown in the Windows app

**Text not appearing?**
- Click on the window/app where you want text to appear before typing on your phone
- The Windows app types wherever your cursor is focused

## Releasing

1. Bump `versionCode` in `android/app/build.gradle.kts` — this must be higher than any build ever uploaded to Google Play, even unpublished ones. `versionName` is the user-visible string and can stay the same (e.g. `"1.0.0"`) across re-uploads.

2. Build Windows EXE:
```bash
cd windows
python -m PyInstaller build.spec
# Output: windows/dist/AirType.exe
```

3. Build Android APK + AAB:
```bash
cd android
./gradlew.bat assembleRelease bundleRelease
# APK: android/app/build/outputs/apk/release/AirType-release.apk
# AAB: android/app/build/outputs/bundle/release/AirType-release.aab (for Google Play)
```

4. Commit and push:
```bash
git add -A
git commit -m "Release vX.X.X"
git push origin main
```

5. Create GitHub release (attach EXE and APK for sideloading; submit AAB to Google Play separately):
```bash
gh release create vX.X.X --title "AirType vX.X.X" \
  windows/dist/AirType.exe \
  android/app/build/outputs/apk/release/AirType-release.apk
```
