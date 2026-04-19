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
- Download `AirType.apk` from [Releases](../../releases)
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

From the repo root:
```bash
build_windows.bat
```

Or invoke PyInstaller directly:
```bash
cd windows
pip install -r requirements.txt
python -m PyInstaller build.spec
```

Output: `windows/dist/AirType-<version>.exe`

### Android App

Requires Android Studio or the Android SDK with Java.

From the repo root, use the build script:
```bash
build_android.bat debug      # or: release, bundle
install_apk.bat              # install the debug or release APK via adb
```

Or invoke Gradle directly:
```bash
cd android
gradlew.bat assembleDebug    # ./gradlew on macOS/Linux
```

Output: `android/app/build/outputs/apk/debug/AirType-debug.apk`

Install manually with:
```bash
adb install android/app/build/outputs/apk/debug/AirType-debug.apk
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

**Windows SmartScreen warning ("Publisher: Unknown")?**
- Expected. The EXE isn't code-signed — I'm not paying for a certificate for a free hobby tool.
- Click **More info → Run anyway**. Or build it yourself from source.

## Releasing

### Versioning

In `android/app/build.gradle.kts`:
- **`versionName`** — user-visible version string (e.g. `"1.1.0"`). Also used in the APK filename (`AirType-1.1.0.apk`). Bump for new releases.
- **`versionCode`** — integer that must increase with every Google Play upload, even unpublished ones. Bump this every time you upload an AAB.

### Build scripts

| Script | What it does |
|---|---|
| `build.bat` | Interactive menu: Android, Windows, or both |
| `build_android.bat [debug\|release\|bundle]` | Build Android APK or AAB (interactive menu if no arg) |
| `build_windows.bat` | Build the Windows EXE |
| `install_apk.bat` | Install the debug or release APK to a connected device via adb |
| `publish.bat` | Build everything (release APK + AAB + EXE), copy APK + EXE to the website deploy dir |
| `release.bat` | Tag, push, and create the GitHub release with all artifacts |

All scripts read `versionName` from `android/app/build.gradle.kts` automatically — no arguments needed.

### Deploy flow

1. Bump `versionName` (and `versionCode` if uploading to Play Store) in `android/app/build.gradle.kts`
2. Update release notes:
   - `release_notes.txt` — GitHub release body (clean markdown)
   - `play_store_notes.txt` — Play Console "What's New" (versioned changelog, wrapped in `<en-GB>` for Play's locale format)
3. Run `publish.bat` — builds everything, copies to website
4. Run `release.bat` — tags, pushes to GitHub, creates release using `release_notes.txt`
5. Upload AAB to Google Play Console manually; paste `play_store_notes.txt` into the release notes field
6. Build and push website:
   ```
   cd C:\gitsync\programming\website
   npm run publish
   cd C:\gitsync\programming\jordanbarnes94.github.io
   git add -A && git commit -m "AirType vX.X.X" && git push
   ```

### Configuration

Signing and deploy settings live in `.env` at the repo root (copy from `.env.example`):
- `AIRTYPE_KEYSTORE_PATH`, `AIRTYPE_KEYSTORE_PASSWORD`, `AIRTYPE_KEY_ALIAS`, `AIRTYPE_KEY_PASSWORD` — Android release signing (read by `android/app/build.gradle.kts`)
- `DEPLOY_DIR` — target directory for the website artifact copy (read by `publish.bat`)

## Developer reference

Architecture notes for anyone hacking on the code:
- [`docs/android-app.md`](docs/android-app.md) — Android source file overview
- [`docs/windows-server.md`](docs/windows-server.md) — Windows server + GUI overview
