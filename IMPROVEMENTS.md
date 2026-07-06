# Improvement Suggestions

> **Status (2026-07):** reviewed and largely implemented on the `claude/app-improvements-fousqr` branch.
> Per-item status is marked below: ✅ done · 🟡 partially done / mitigated · ❌ deliberately skipped (with reason).

Findings from a codebase review covering the Windows server (`windows/`), the Android app (`android/`), and the repo tooling. Items are grouped by priority: **worth doing** fixes real problems; **nice to have** is polish that can wait. AirType is a personal project used on a trusted home network, so suggestions are framed proportionately — not everything here needs doing.

## 1. Security (worth doing)

### 1.1 No authentication on the WebSocket — ✅ done

The server accepts any connection and types whatever it receives. It binds to all interfaces (`windows/server.py`, the `"0.0.0.0"` bind in `start()`), so **any device on the same WiFi can inject arbitrary keystrokes into the PC** — on a home network this is a small risk, but on shared WiFi (office, flat share, public hotspot) it's effectively remote code execution via `Win+R`.

A pragmatic fix that avoids TLS complexity:

- Generate a short pairing token on the server (show it in the GUI / CLI banner).
- Require the first WebSocket message to be `{"type": "auth", "token": "..."}`; close the connection otherwise.
- Store the token on the Android side in SharedPreferences after first entry.

### 1.2 Plaintext traffic — 🟡 mitigated (token auth + README warning; TLS deferred as suggested)

Everything typed travels unencrypted: the client hardcodes `ws://` (`android/.../WebSocketClient.kt`) and the manifest sets `android:usesCleartextTraffic="true"` (`android/app/src/main/AndroidManifest.xml`). Anyone sniffing the LAN can read passwords or anything else typed through the app.

Full fix is `wss://` with TLS, but self-signed certs on a LAN are awkward (cert pinning or a trust-on-first-use prompt on Android). Reasonable middle ground: do 1.1 first, document the plaintext limitation prominently in the README ("don't type passwords through AirType on untrusted networks"), and treat TLS as a later milestone.

### 1.3 Typed content leaks to logcat — ✅ done (content removed from log messages entirely)

`WebSocketClient.kt` and `MainActivity.kt` log message contents at debug level. Anything typed (including passwords) ends up in logcat. Gate these behind `if (BuildConfig.DEBUG)` or strip them in release builds.

## 2. Robustness — Android (worth doing)

- ✅ **Coroutine scope leak on rotation.** `WebSocketClient` creates `CoroutineScope(Dispatchers.IO)` and never cancels it; `MainActivity.onCreate()` builds a fresh client each time, so every configuration change leaks a scope with possibly-pending reconnect jobs. Add a `close()` that cancels the scope and call it from `onDestroy()` — or hold the client in a `ViewModel` so it survives rotation.
- ✅ **Reconnect retries forever.** `RECONNECT_DELAY_MS = 3_000L` with no cap or backoff means a phone left running against a dead server retries every 3 s indefinitely (battery drain). Use exponential backoff (3 s → 6 s → 12 s, capped at ~60 s) and/or a max attempt count with a "tap to retry" state.
- ✅ **No IP/port validation.** `MainActivity` passes the IP straight through, and an invalid port silently falls back to 8765 (`toIntOrNull() ?: 8765`), which connects the user somewhere they didn't intend with no feedback. Validate both and show a toast on bad input.
- ✅ **Unsynchronized connection state.** `isConnected()` reads the `webSocket` field from the UI thread while coroutines write it; mark the field `@Volatile`.

## 3. Robustness — Windows server (worth doing)

- ✅ **Unbounded message queue.** `asyncio.Queue()` in `server.py` has no `maxsize`; a fast or misbehaving client can grow memory without bound while pyautogui types at human speed. Use `asyncio.Queue(maxsize=200)` and drop/refuse when full.
- ✅ **No graceful shutdown.** The `ThreadPoolExecutor` is never shut down and `wait_closed()` has no timeout, so `stop()` can hang or leak threads. Add `executor.shutdown()` in a `finally` block and wrap shutdown awaits in `asyncio.wait_for(...)`.
- ✅ **GUI port-restart race.** `gui.py` waits a fixed 500 ms before restarting on a new port; if the old socket isn't released yet, the new bind fails with no retry. Wait on the actual server-stopped signal, or retry the bind a few times.
- ✅ **Missing port validation in the GUI.** The port entry only catches `ValueError`; out-of-range values (0, 70000) reach `websockets.serve()` and fail cryptically. Validate `1024 <= port <= 65535` first.
- ✅ **Silent `except Exception: pass` blocks** in `gui.py` (DPI setup, icon loading) hide real failures. At minimum, log them.

## 4. Testing & CI (worth doing)

- ✅ **No tests for the Python server.** The Android side has a solid precedent (`TextSyncProcessorTest.kt` — 16 cases covering emoji/grapheme handling), but `server.py`'s message parsing and queue handling have none. The `process_message()` logic is easy to unit-test with pytest by mocking pyautogui.
- ✅ **No CI.** There's no `.github/workflows/`. A single workflow running the Android unit tests (`gradlew test`) and Python tests/lint on push would catch regressions before release — especially valuable since releases are built locally by hand.

## 5. Release & dependency hygiene (nice to have)

- ✅ **Loose dependency pins.** `windows/requirements.txt` uses `>=` with no upper bounds; a major bump in `websockets` or `pillow` can silently break a local build. Pin upper bounds (`websockets>=12.0,<13`) or commit a lock file generated with `pip freeze`.
- ✅ **Release checklist gaps.** `play_store_notes.txt` still says v1.0.0 while the project is at v1.1.0, and `release.bat` doesn't verify it was updated, nor that the `gh` CLI is installed. A couple of pre-flight checks in the script would prevent stale store listings.
- ✅ **Add a `CHANGELOG.md`** so release history lives in the repo rather than only in GitHub Releases.

## 6. Smaller polish (nice to have)

- ❌ (skipped — mDNS/QR pairing is a bigger feature than this pass warranted) Hardcoded default IP `192.168.1.100` in `MainActivity.kt` — consider mDNS discovery or a QR code shown by the Windows app so users never type an IP.
- ❌ (skipped — no config sprawl yet to justify it) `gui.py` hardcodes the AppUserModelID and window sizes; fine for now, worth centralizing if more config appears.
- ✅ (marked `importantForAccessibility="no"` — the adjacent `statusText` already announces the state) `statusDot` in `activity_main.xml` has no `contentDescription`, so the connection state is invisible to screen readers.
- ✅ Unused `msg_type` return value from `process_message()` in `server.py` — leftover from a refactor.

## What's already good

Worth saying explicitly: the architecture docs in `docs/` are unusually thorough for a project this size, `TextSyncProcessor` is cleanly decoupled and well-tested, secrets are handled properly (`.env` + `.gitignore`, nothing hardcoded), and the version single-sourcing from `build.gradle.kts` across all the build scripts is a nice touch.

## Additional findings addressed in the same pass

Issues found during implementation that the original review missed:

- ✅ **Unbounded/untyped `backspace.count`.** A client could send `{"count": 10**9}` (minutes of held backspace) or a non-integer that crashed the handler thread. Counts are now type-checked and clamped to 1–500; text content is capped at 5000 chars per message.
- ✅ **Non-dict JSON crashed message processing.** A frame like `"hello"` or `[1,2]` parsed as valid JSON but blew up on `msg.get(...)` in the executor. All messages now pass through `sanitize_message()` before queueing.
- ✅ **Auth failures retried forever.** With token auth added, a wrong token would have hit the reconnect loop indefinitely; the client now stops reconnecting on close code 4401 and tells the user.
- ✅ **GUI settings were read-only.** `config.json` was loaded but never written; mode/port/token changes now persist across restarts.
- ✅ **Server startup failures were invisible in the GUI.** A failed bind was logged to a console nobody sees; it now surfaces in the activity log.
