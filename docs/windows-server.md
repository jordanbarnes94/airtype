# AirType Windows Server

Python WebSocket server that receives typing commands from the Android app and simulates keystrokes on the PC using pyautogui.

## Source Files

All in `windows/`

### server.py
Core server logic, shared between CLI and GUI frontends.

**`AirTypeServer` class:**
- Async WebSocket server via `websockets` library, listens on `0.0.0.0:<port>` (default 8765)
- Optional pairing token: when `token` is set, the first frame from a client must be `{"type": "auth", "token": "..."}` (10s timeout); the server replies `{"type": "auth_ok"}` or closes with code 4401
- Incoming JSON messages are validated by `sanitize_message()` (must be a dict of a known type; text capped at 5000 chars, backspace count clamped to 1–500) and placed into a bounded `asyncio.Queue` (256 entries, drops with a warning when full)
- A dedicated queue processor task pulls messages sequentially and runs them in a `ThreadPoolExecutor(max_workers=1)` — ensures keystrokes execute in order and don't overlap
- Callbacks: `on_connect(ip)`, `on_disconnect(ip)`, `on_message(description)`, `on_error(error)` — used by both frontends
- `stop()` sets an asyncio Event to signal shutdown; `start()`'s cleanup bounds the close wait (5s) and shuts down the executor

**Message processing (`process_message`):**
- `{"type": "text", "content": "..."}` → ASCII mode: `pyautogui.write(content, interval=interval)` types character by character. Unicode mode: `pyperclip.copy(content)` + `pyautogui.hotkey('ctrl', 'v')` pastes via clipboard
- `{"type": "backspace", "count": N}` → `pyautogui.press('backspace', presses=N, interval=interval)`
- `{"type": "enter"}` → `pyautogui.press('enter')`

**Key setting:** `pyautogui.PAUSE = 0` at module level — disables the default 0.1s pause between pyautogui actions for responsiveness.

**`get_local_ip()`:** Discovers the machine's LAN IP by creating a UDP socket to 8.8.8.8 and reading the local address. Falls back to 127.0.0.1.

### main.py
CLI frontend. Argparse-based.

- `--mode ascii|unicode` — typing mode (default: ascii)
- `--port N` — WebSocket port (default: 8765, validated to 1–65535)
- `--token TOKEN` — require clients to authenticate with this pairing token (default: no auth)
- `--debug` — verbose logging
- `--silent` — minimal output
- Prints the local IP and port for the user to enter on their phone
- Creates `AirTypeServer` and runs it with `asyncio.run()`

### gui.py
GUI frontend using customtkinter (dark theme) + pystray (system tray).

**Main window (400x620):**
- Connection info: shows IP address, port, and pairing token
- Status: "Waiting for connection..." / "Connected (ip)"
- Settings: mode dropdown (ASCII / Unicode clipboard), port input, token input, restart server button (port validated to 1024–65535; restart waits for the old server thread to exit before rebinding)
- Bottom: "Minimize to Tray" and "Quit" buttons

**Activity log panel:**
- Hidden by default, toggled with "Show activity log" checkbox
- Slides out on the right, expanding window to 780px
- Timestamped log of all received messages, capped at 1000 lines

**System tray (pystray):**
- Closing the window minimizes to tray (not quit)
- Tray menu: Open / Quit
- Icon loaded from `airtype_tray.png` or `airtype.ico`, pre-sized to DPI-appropriate dimensions

**Windows display fixes:**
- `SetProcessDpiAwareness(2)` — per-monitor DPI awareness, prevents blurry scaling
- `SetCurrentProcessExplicitAppUserModelID("click.jordanbarnes.airtype")` — shows app icon in taskbar instead of python.exe icon
- `_set_taskbar_icon()` — overrides Tk's hardcoded 32px ICON_BIG with DPI-correct size via `WM_SETICON` and `SetClassLongPtrW`

**Threading model:**
- Server runs in a daemon thread with its own asyncio event loop
- Server callbacks are marshaled to the main (Tk) thread via `self.after(0, callback)` using `_schedule_*` methods

**Config (`config.json`):**
```json
{"port": 8765, "keypress_interval": 0.01, "mode": "ascii", "token": "ABC123"}
```
- `keypress_interval` — delay in seconds between individual simulated key presses (pyautogui `interval` param)
- `token` — pairing token, generated on first GUI run; set to `""` to disable authentication
- Settings changed in the GUI (mode, port, token) are persisted back to this file

## Dependencies

`requirements.txt`:
- `websockets` — async WebSocket server
- `pyautogui` — keyboard/mouse simulation
- `pyperclip` — clipboard access (for Unicode mode)
- `pystray` — system tray icon
- `pillow` — image handling for tray icon
- `customtkinter` — modern Tk GUI

## Tests

`windows/test_server.py` — pytest suite covering message sanitization, clamping, and the auth handshake (pyautogui/pyperclip are mocked, so it runs headless: `pytest windows/`). Runs in CI via `.github/workflows/ci.yml`.
- `pyinstaller` — builds standalone .exe

## Build

- `build_windows.bat` — runs `python -m PyInstaller build.spec --noconfirm`
- Produces `windows/dist/AirType.exe`

## Protocol

All communication is **one-directional: Android → Windows**. The server never sends messages back. Three message types: `text`, `backspace`, `enter` (see server.py above).

## ASCII vs Unicode Mode

- **ASCII (default):** `pyautogui.write()` simulates individual keystrokes. Fast, works everywhere, but limited to ASCII characters.
- **Unicode (clipboard):** Copies text to clipboard via pyperclip, then simulates Ctrl+V. Supports all characters but overwrites the user's clipboard contents.
