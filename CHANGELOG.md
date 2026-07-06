# Changelog

## Unreleased (v1.2.0)

### Security
- Optional pairing token: the Windows app now generates a short token on first run and requires the phone to send it before any typing is accepted. Set the token field to empty (or `"token": ""` in `config.json`) to disable. The CLI supports `--token`.
- Typed content no longer appears in Android logcat.
- Server validates and bounds all incoming messages (text length, backspace count, message shape) and caps its processing queue.

### Fixed
- Android reconnect now backs off exponentially (3s doubling to a 60s cap) instead of hammering every 3 seconds forever.
- Android no longer leaks a coroutine scope on every configuration change; resources are released in `onDestroy`.
- Invalid port numbers on Android show an error instead of silently connecting to 8765.
- Authentication failures stop the reconnect loop and tell the user, instead of retrying a wrong token forever.
- GUI "Restart Server" now waits for the old server to actually stop instead of a fixed 500 ms, avoiding failed rebinds.
- GUI validates the port range before restarting.
- Server shuts down its typing thread pool and bounds shutdown waits, so quitting can't hang.

### Added
- Pytest suite for the Windows server (message validation, clamps, auth handshake).
- GitHub Actions CI running the Python and Android test suites.
- GUI settings (mode, port, token) now persist to `config.json`.
- `release.bat` preflight checks: `gh` CLI present, Play Store notes not stale.
- Dependency upper bounds in `requirements.txt`.

## v1.1.0 — 2026

- Grapheme-aware backspace: deleting an emoji on the phone deletes the whole emoji on the PC.
- Keyboard-aware layout: connection card hides while typing so the text area stays visible.
- UX polish.

## v1.0.0

- Initial release: Android app + Windows server (GUI with system tray, CLI), WebSocket-based real-time typing with glide typing, autocorrect, and voice input support.
