# AirType Android App

Kotlin app that turns your phone into a wireless keyboard for your Windows PC. Connects to the Windows server over WebSocket on your local network and sends keystroke commands as JSON.

## Source Files

All in `android/app/src/main/java/click/jordanbarnes/airtype/`

### MainActivity.kt
UI controller. Single-activity app.

- **Connection card:** IP + port inputs (persisted in SharedPreferences), connect/disconnect button, status dot + text
- **Text input area:** Uses `AppendOnlyEditText` (custom view). Has a clear button that resets local text without sending anything to the PC (`ignoreTextChanges = true` during clear)
- **Typing flow:** `TextWatcher` fires on every keystroke → delegates to `TextSyncProcessor.onTextChanged()` → processor calls `sendText()` / `sendBackspace()` / `sendEnter()` on the `WebSocketClient`
- **Backspace on empty:** When the EditText is already empty and the user hits backspace, the backspace is still forwarded to the PC. Two code paths handle this:
  - Soft keyboard: `AppendOnlyEditText.onBackspaceWhenEmpty` callback (fires from InputConnection)
  - Hardware/Bluetooth keyboard: `setOnKeyListener` checking `KEYCODE_DEL`
- **`suppressKeyBackspace` flag:** Prevents double-sending when both paths fire for the same backspace event. Set to true, then cleared on next UI frame via `post{}`
- **Reconnect UI:** Shows "Reconnecting (attempt N)..." and keeps the disconnect button visible during reconnect attempts

### WebSocketClient.kt
WebSocket transport layer using OkHttp.

- Connects to `ws://<ip>:<port>`
- **JSON message formats:**
  - `{"type": "text", "content": "hello"}`
  - `{"type": "backspace", "count": 3}`
  - `{"type": "enter"}`
- **Auto-reconnect:** On connection loss (unless user manually disconnected via `isUserDisconnected` flag), retries every 3 seconds via coroutine. Reports attempt number to UI
- **Send failure detection:** If `ws.send()` returns false, treats connection as dead → triggers reconnect
- **Error filtering:** Suppresses toasts for expected disconnect errors (Broken pipe, Connection reset, Connection abort)
- Messages from server are logged but otherwise ignored (protocol is one-directional)

### TextSyncProcessor.kt
Diff engine that converts TextWatcher events into typing commands.

- Hooks into both `beforeTextChanged` and `onTextChanged` from `TextWatcher`
- `beforeTextChanged` captures the deleted substring so backspace count can be measured in grapheme clusters (not raw UTF-16 code units). This means emoji like 😀 (2 code units) or flags like 🇦🇺 (4 code units) each count as 1 backspace
- `before > 0` → sends `sendBackspace(graphemeCount)`
- `count > 0` → extracts new substring, sends `sendText()`. If it contains `\n`, splits and sends alternating `sendText()` / `sendEnter()`
- Handles autocorrect: keyboard replaces "teh" with "the" → `before=3, count=3` → sends 3 backspaces then "the"
- Extracted into its own class with a `MessageSender` interface for unit testability

### AppendOnlyEditText.kt
Custom `AppCompatEditText` that locks the cursor to the end of text at all times. This is critical because `TextSyncProcessor` only works when changes happen at the end.

**What it prevents and how:**
- **Tap to reposition cursor:** `onTouchEvent` posts `moveCursorToEnd()` on ACTION_DOWN and ACTION_UP
- **Spacebar-swipe cursor repositioning (Gboard):** `onSelectionChanged` detects `selStart == selEnd` with cursor not at end → posts `moveCursorToEnd()`
- **Text selection:** `setTextIsSelectable(false)`, `isLongClickable = false`, action mode callbacks blocked
- **Cut/Copy/Select All keyboard shortcuts:** Blocked in `onTextContextMenuItem`

**What it allows carefully:**
- **Gboard swipe-delete gesture:** When user holds backspace and swipes left, Gboard creates a selection (`selStart != selEnd`). The code does NOT snap back during this — waits for `deleteSurroundingText` to fire, then snaps after. Previous 150ms timer approach broke on long swipe-holds.
- **InputConnection wrapping:** Wraps the base InputConnection to intercept `commitText` and `deleteSurroundingText`. Before text insertion: synchronous snap to end. After deletion: posted snap to end. This guarantees text is always appended.
- **Empty backspace forwarding:** `deleteSurroundingText` on empty text → calls `onBackspaceWhenEmpty` callback

**`moveCursorToEnd()`:** Has a guard to avoid no-op `setSelection()` calls, which would trigger `onSelectionChanged` again and loop infinitely.

### TextSyncProcessorTest.kt
`android/app/src/test/java/click/jordanbarnes/airtype/`

13 unit tests covering: normal typing, multi-char, backspace (plus emoji and flag-emoji grapheme handling, fallback when `beforeTextChanged` wasn't captured), autocorrect, glide typing, enter, text with newlines, multiple newlines, and null / no-change.

## Layout & Resources

- `activity_main.xml` — Single layout: header bar (title + status dot), connection card (IP/port inputs + connect button), text input area (AppendOnlyEditText + clear button)
- Dark theme with custom drawables for buttons, cards, edit text backgrounds, status dots
- `AndroidManifest.xml` — Requires INTERNET and ACCESS_NETWORK_STATE permissions. `usesCleartextTraffic=true` for `ws://`. `windowSoftInputMode=adjustResize` so keyboard doesn't cover the text input.

## Build

- Gradle Kotlin DSL. AGP 8.5.0, Kotlin 1.9.21
- `compileSdk = 36`, `minSdk = 26`, `targetSdk = 36`
- Dependencies: AndroidX (appcompat, activity-ktx, core-ktx), OkHttp 4.12.0, Kotlin Coroutines 1.7.3, JUnit 4
- Release signing config reads from `.env` file in repo root (AIRTYPE_KEYSTORE_PATH, etc.)
- Output APK named `AirType-debug.apk` (debug) / `AirType-{version}.apk` (release)
- Build via `build_android.bat [debug|release|bundle]`
