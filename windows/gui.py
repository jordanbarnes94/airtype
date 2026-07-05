#!/usr/bin/env python3
"""
AirType - GUI Application
"""

import asyncio
import json
import logging
import os
import secrets
import sys
import threading
from datetime import datetime
from typing import Optional

import customtkinter as ctk
import pystray
from PIL import Image

from server import AirTypeServer, get_local_ip

# Get the directory where this script is located (works for both dev and PyInstaller)
if getattr(sys, "frozen", False):
    SCRIPT_DIR = sys._MEIPASS
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ICON_PATH = os.path.join(SCRIPT_DIR, "airtype.ico")
TRAY_ICON_PATH = os.path.join(SCRIPT_DIR, "airtype_tray.png")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logging.getLogger("airtype").warning(f"Could not save config: {e}")


def generate_token() -> str:
    """Generate a short pairing token, avoiding easily-confused characters."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))

# Windows display fixes (must run before any window is created):
# 1. DPI awareness - without this, Windows bitmap-scales the process,
#    making the taskbar icon (and everything else) blurry.
# 2. AppUserModelID - without this, Windows groups the window under
#    python.exe and uses its icon instead of ours.
try:
    import ctypes

    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception as e:
    logging.getLogger("airtype").debug(f"SetProcessDpiAwareness failed: {e}")
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as e2:
        logging.getLogger("airtype").debug(f"SetProcessDPIAware failed: {e2}")

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "click.jordanbarnes.airtype"
    )
except Exception as e:
    logging.getLogger("airtype").debug(f"SetCurrentProcessExplicitAppUserModelID failed: {e}")

logger = logging.getLogger("airtype")

LOG_MAX_LINES = 1000


class AirTypeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # App state
        self.server: Optional[AirTypeServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.tray_icon: Optional[pystray.Icon] = None

        config = load_config()
        self.mode = config.get("mode", "ascii")
        self.port = config.get("port", 8765)
        self.interval = config.get("keypress_interval", 0.01)
        # Pairing token: generated on first run; set "token": "" in config.json
        # (or clear the Token field) to disable authentication.
        if "token" in config:
            self.token = config.get("token") or ""
        else:
            self.token = generate_token()
            config["token"] = self.token
            save_config(config)

        # Window setup
        self.title("AirType")
        self.geometry("400x620")
        self.minsize(350, 500)

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Set window icon.
        # iconbitmap() calls Tk's WinSetIcon which sends both WM_SETICON
        # ICON_SMALL (16px) and ICON_BIG, but Tk hardcodes ICON_BIG to 32x32
        # regardless of DPI.  We override ICON_BIG via ctypes after a delay
        # (past CTk's 200ms icon timer and Tk's window-mapping WM_SETICON).
        if os.path.exists(ICON_PATH):
            self.iconbitmap(ICON_PATH)
            self.after(300, self._set_taskbar_icon)

        self.create_widgets()
        self.start_server()

    def _set_taskbar_icon(self):
        """Override ICON_BIG with a DPI-appropriate icon for the taskbar.

        Tk hardcodes ICON_BIG to 32x32 in its C code (tkWinWm.c GetIcon()).
        On high-DPI displays the taskbar needs 48px (150%) or 64px (200%).
        We load the .ico at the correct size and set it via both WM_SETICON
        and SetClassLongPtrW (Windows 11 taskbar may read the class icon).
        """
        try:
            user32 = ctypes.windll.user32

            SM_CXICON = 11
            WM_SETICON = 0x0080
            ICON_BIG = 1
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            GCLP_HICON = -14

            # DPI-appropriate large icon size (32 at 100%, 48 at 150%, 64 at 200%)
            size = user32.GetSystemMetrics(SM_CXICON) or 32

            hicon = user32.LoadImageW(
                None, ICON_PATH, IMAGE_ICON, size, size, LR_LOADFROMFILE
            )
            if not hicon:
                return

            # wm_frame() returns the WM wrapper HWND (hex string like "0x1234")
            try:
                hwnd = int(self.wm_frame(), 0)
            except Exception:
                hwnd = user32.GetParent(self.winfo_id())

            if hwnd:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
                user32.SetClassLongPtrW(hwnd, GCLP_HICON, hicon)
        except Exception as e:
            logger.debug(f"Taskbar icon override failed: {e}")

    def create_widgets(self):
        # Container for main + log panel side by side
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        # Main panel (left side)
        self.main_frame = ctk.CTkFrame(self.container)
        self.main_frame.pack(side="left", fill="both", expand=True)

        # Log panel (right side) - starts hidden
        self.log_frame = ctk.CTkFrame(self.container, width=350)
        # Don't pack yet - will be shown when checkbox is ticked

        # === Main panel contents ===
        # Bottom-anchored widgets must be packed first so they're always visible

        # Bottom buttons
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        self.tray_btn = ctk.CTkButton(
            btn_frame,
            text="Minimize to Tray",
            command=self.minimize_to_tray,
            width=130,
            height=32,
        )
        self.tray_btn.pack(side="left")

        self.quit_btn = ctk.CTkButton(
            btn_frame,
            text="Quit",
            command=self.quit_app,
            width=80,
            height=32,
            fg_color="#8B0000",
            hover_color="#A52A2A",
        )
        self.quit_btn.pack(side="right")

        # Show activity log checkbox
        self.show_debug_var = ctk.BooleanVar(value=False)
        debug_check = ctk.CTkCheckBox(
            self.main_frame,
            text="Show activity log",
            variable=self.show_debug_var,
            command=self.toggle_debug,
        )
        debug_check.pack(side="bottom", pady=(5, 10))

        # Title with more top padding
        title_label = ctk.CTkLabel(
            self.main_frame, text="AirType", font=ctk.CTkFont(size=22, weight="bold")
        )
        title_label.pack(pady=(15, 15))

        # Connection info frame
        conn_frame = ctk.CTkFrame(self.main_frame)
        conn_frame.pack(fill="x", padx=10, pady=(0, 10))

        conn_label = ctk.CTkLabel(
            conn_frame, text="Connect your phone to:", font=ctk.CTkFont(size=12)
        )
        conn_label.pack(pady=(10, 8))

        # IP and Port side-by-side display boxes (75% / 25%)
        boxes_frame = ctk.CTkFrame(conn_frame, fg_color="transparent")
        boxes_frame.pack(fill="x", padx=10, pady=(0, 12))
        boxes_frame.columnconfigure(0, weight=3)
        boxes_frame.columnconfigure(1, weight=1)

        # IP box
        ip_box = ctk.CTkFrame(boxes_frame)
        ip_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkLabel(ip_box, text="IP Address", font=ctk.CTkFont(size=11)).pack(pady=(5, 0))
        self.ip_display = ctk.CTkLabel(
            ip_box,
            text=get_local_ip(),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=("#1E90FF", "#00BFFF"),
        )
        self.ip_display.pack(pady=(0, 5))

        # Port box
        port_box = ctk.CTkFrame(boxes_frame)
        port_box.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(port_box, text="Port", font=ctk.CTkFont(size=11)).pack(pady=(5, 0))
        self.port_display = ctk.CTkLabel(
            port_box,
            text=str(self.port),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=("#1E90FF", "#00BFFF"),
        )
        self.port_display.pack(pady=(0, 5))

        # Pairing token box (full width, below IP/port)
        token_box = ctk.CTkFrame(conn_frame)
        token_box.pack(fill="x", padx=10, pady=(0, 12))

        ctk.CTkLabel(token_box, text="Pairing Token", font=ctk.CTkFont(size=11)).pack(pady=(5, 0))
        self.token_display = ctk.CTkLabel(
            token_box,
            text=self.token if self.token else "(authentication disabled)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=("#1E90FF", "#00BFFF") if self.token else ("#B8860B", "#FFA500"),
        )
        self.token_display.pack(pady=(0, 5))

        # Status frame
        status_frame = ctk.CTkFrame(self.main_frame)
        status_frame.pack(fill="x", padx=10, pady=(0, 10))

        status_title = ctk.CTkLabel(
            status_frame, text="Status", font=ctk.CTkFont(size=12)
        )
        status_title.pack(pady=(10, 5))

        self.status_label = ctk.CTkLabel(
            status_frame, text="Waiting for connection...", font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(pady=(0, 10))

        # Settings frame
        settings_frame = ctk.CTkFrame(self.main_frame)
        settings_frame.pack(fill="x", padx=10, pady=(0, 10))

        settings_title = ctk.CTkLabel(
            settings_frame, text="Settings", font=ctk.CTkFont(size=14, weight="bold")
        )
        settings_title.pack(pady=(10, 5))

        # Mode selection
        mode_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        mode_frame.pack(fill="x", padx=10, pady=(0, 5))

        mode_label = ctk.CTkLabel(mode_frame, text="Mode:")
        mode_label.pack(side="left")

        self.mode_var = ctk.StringVar(value="ASCII")
        self.mode_menu = ctk.CTkOptionMenu(
            mode_frame,
            values=["ASCII", "Unicode (clipboard)"],
            variable=self.mode_var,
            command=self.on_mode_change,
            width=150,
        )
        self.mode_menu.pack(side="right")

        # Port setting
        port_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        port_frame.pack(fill="x", padx=10, pady=(5, 5))

        port_label = ctk.CTkLabel(port_frame, text="Port:")
        port_label.pack(side="left")

        self.port_entry = ctk.CTkEntry(port_frame, width=70)
        self.port_entry.insert(0, str(self.port))
        self.port_entry.pack(side="right")

        # Token setting
        token_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        token_frame.pack(fill="x", padx=10, pady=(5, 5))

        token_label = ctk.CTkLabel(token_frame, text="Token:")
        token_label.pack(side="left")

        self.token_entry = ctk.CTkEntry(token_frame, width=110)
        self.token_entry.insert(0, self.token)
        self.token_entry.pack(side="right")

        # Restart button for port changes
        self.restart_btn = ctk.CTkButton(
            settings_frame,
            text="Restart Server",
            command=self.restart_server,
            width=140,
            height=28,
        )
        self.restart_btn.pack(pady=(5, 10))

        # === Log panel contents ===
        log_title = ctk.CTkLabel(
            self.log_frame,
            text="Activity Log",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        log_title.pack(pady=(10, 5))

        self.log_text = ctk.CTkTextbox(self.log_frame)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def toggle_debug(self):
        """Toggle debug log visibility by showing/hiding the side panel."""
        if self.show_debug_var.get():
            # Show log panel, widen window
            self.log_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))
            self.geometry("780x620")
        else:
            # Hide log panel, shrink window
            self.log_frame.pack_forget()
            self.geometry("400x620")

    def log(self, message: str):
        """Add a message to the log display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > LOG_MAX_LINES:
            self.log_text.delete("1.0", f"{line_count - LOG_MAX_LINES + 1}.0")
        self.log_text.see("end")

    def on_mode_change(self, choice: str):
        """Handle mode selection change."""
        new_mode = "unicode" if "Unicode" in choice else "ascii"
        self.mode = new_mode
        if self.server:
            self.server.mode = new_mode
        self._persist_config()
        self.log(f"Mode changed to: {self.mode.upper()}")

    def _persist_config(self):
        config = load_config()
        config.update({"mode": self.mode, "port": self.port, "token": self.token})
        save_config(config)

    def update_status(self, connected: bool, client_ip: Optional[str] = None):
        """Update the connection status display."""
        if connected:
            self.status_label.configure(
                text=f"Connected ({client_ip})", text_color=("#00AA00", "#00FF00")
            )
        else:
            self.status_label.configure(
                text="Waiting for connection...", text_color=("gray60", "gray40")
            )

    def _schedule_connect(self, ip: str):
        """Schedule connect callback on main thread."""
        self.after(0, lambda i=ip: self._on_connect(i))

    def _schedule_disconnect(self, ip: str):
        """Schedule disconnect callback on main thread."""
        self.after(0, lambda i=ip: self._on_disconnect(i))

    def _schedule_message(self, msg: str):
        """Schedule message callback on main thread."""
        self.after(0, lambda m=msg: self.log(m))

    def _schedule_error(self, err: str):
        """Schedule error callback on main thread."""
        self.after(0, lambda e=err: self.log(f"Error: {e}"))

    def start_server(self):
        """Start the WebSocket server in a background thread."""
        self.server = AirTypeServer(
            port=self.port,
            mode=self.mode,
            interval=self.interval,
            token=self.token,
            on_connect=self._schedule_connect,
            on_disconnect=self._schedule_disconnect,
            on_message=self._schedule_message,
            on_error=self._schedule_error,
        )

        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.server.start())
            except Exception as e:
                logger.error(f"Server error: {e}")
                self._schedule_error(f"Server failed to start: {e}")

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.log(f"Server started on port {self.port}")

    def _on_connect(self, ip: str):
        """Handle client connection (called on main thread)."""
        self.update_status(True, ip)
        self.log(f"Client connected: {ip}")

    def _on_disconnect(self, ip: str):
        """Handle client disconnection (called on main thread)."""
        self.update_status(False)
        self.log(f"Client disconnected: {ip}")

    def restart_server(self):
        """Restart the server with new port/token settings."""
        try:
            new_port = int(self.port_entry.get())
        except ValueError:
            self.log("Invalid port number")
            return
        if not 1024 <= new_port <= 65535:
            self.log(f"Port must be between 1024 and 65535 (got {new_port})")
            return

        # Stop old server
        if self.server:
            self.server.stop()
            self.log("Stopping server...")

        # Apply new settings
        self.port = new_port
        self.token = self.token_entry.get().strip()
        self._persist_config()
        self.ip_display.configure(text=get_local_ip())
        self.port_display.configure(text=str(self.port))
        self.token_display.configure(
            text=self.token if self.token else "(authentication disabled)",
            text_color=("#1E90FF", "#00BFFF") if self.token else ("#B8860B", "#FFA500"),
        )

        # Start the new server once the old one has actually stopped
        # (waiting a fixed delay risks the port still being bound)
        self._start_when_stopped(attempts_left=50)

    def _start_when_stopped(self, attempts_left: int):
        """Poll until the old server thread exits, then start the new server."""
        if self.server_thread and self.server_thread.is_alive():
            if attempts_left <= 0:
                self.log("Old server did not stop in time; starting anyway")
            else:
                self.after(100, lambda: self._start_when_stopped(attempts_left - 1))
                return
        self.start_server()

    def create_tray_icon(self) -> Image.Image:
        """Load the tray icon, pre-sized for the system tray.

        pystray's Win32 backend loads icons at SM_CXICON (32px at 100% DPI)
        then Windows downscales to SM_CXSMICON for the tray. We pre-resize to
        SM_CXICON so LoadImage gets an exact match and only one downscale occurs.
        """
        # Query the large icon size that pystray's LoadImage will request
        try:
            import ctypes

            SM_CXICON = 11
            target = ctypes.windll.user32.GetSystemMetrics(SM_CXICON)
            if target <= 0:
                target = 32
        except Exception as e:
            logger.debug(f"GetSystemMetrics failed, using 32px tray icon: {e}")
            target = 32

        if os.path.exists(TRAY_ICON_PATH):
            img = Image.open(TRAY_ICON_PATH)
        elif os.path.exists(ICON_PATH):
            img = Image.open(ICON_PATH)
        else:
            # Fallback: create a simple icon programmatically
            from PIL import ImageDraw

            img = Image.new("RGB", (64, 64), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            draw.polygon(
                [(32, 8), (8, 56), (18, 56), (25, 40), (39, 40), (46, 56), (56, 56)],
                outline=(0, 191, 255),
                fill=None,
            )
            draw.line([28, 32, 36, 32], fill=(0, 191, 255), width=3)

        return img.resize((target, target), Image.LANCZOS)

    def minimize_to_tray(self):
        """Minimize the window to system tray."""
        self.withdraw()

        def on_tray_click(icon, item):
            icon.stop()
            self.after(0, self.deiconify)

        def on_quit(icon, item):
            icon.stop()
            self.after(0, self.quit_app)

        menu = pystray.Menu(
            pystray.MenuItem("Open", on_tray_click, default=True),
            pystray.MenuItem("Quit", on_quit),
        )

        self.tray_icon = pystray.Icon(
            "AirType", self.create_tray_icon(), "AirType", menu
        )

        # Run tray icon in separate thread
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def on_close(self):
        """Handle window close button."""
        self.minimize_to_tray()

    def quit_app(self):
        """Quit the application completely."""
        if self.server:
            self.server.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    app = AirTypeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
