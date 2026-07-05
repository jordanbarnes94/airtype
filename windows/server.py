#!/usr/bin/env python3
"""
AirType - Core Server Logic
Shared between CLI (main.py) and GUI (gui.py)
"""

import asyncio
import hmac
import json
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import websockets
import pyautogui

# Disable PyAutoGUI's pause between actions for responsiveness
pyautogui.PAUSE = 0

logger = logging.getLogger("airtype")

# Sanity limits on incoming messages. A well-behaved client never gets near
# these; they exist so a buggy or hostile client can't wedge the server.
MAX_TEXT_LENGTH = 5000
MAX_BACKSPACE_COUNT = 500
MAX_QUEUE_SIZE = 256
AUTH_TIMEOUT_SECONDS = 10
CLOSE_CODE_AUTH_FAILED = 4401


def get_local_ip() -> str:
    """Get the local IP address for display to user."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def handle_text(content: str, mode: str, interval: float):
    """Handle text message - type the content."""
    logger.debug(f"[TEXT] '{content}' (len={len(content)})")

    if mode == "unicode":
        import pyperclip
        pyperclip.copy(content)
        pyautogui.hotkey('ctrl', 'v')
        logger.debug("[TEXT] pasted via clipboard")
    else:
        pyautogui.write(content, interval=interval)
        logger.debug(f"[TEXT] typed {len(content)} chars")


def handle_backspace(count: int, interval: float):
    """Handle backspace message - press backspace key."""
    logger.debug(f"[BACKSPACE] x{count}")
    pyautogui.press('backspace', presses=count, interval=interval)


def handle_enter():
    """Handle enter message - press enter key."""
    logger.debug("[ENTER]")
    pyautogui.press('enter')


def sanitize_message(msg) -> Optional[dict]:
    """
    Validate and normalize a decoded client message.
    Returns a safe dict, or None if the message is malformed.
    """
    if not isinstance(msg, dict):
        return None

    msg_type = msg.get("type")
    if msg_type == "text":
        content = msg.get("content", "")
        if not isinstance(content, str):
            return None
        return {"type": "text", "content": content[:MAX_TEXT_LENGTH]}
    elif msg_type == "backspace":
        count = msg.get("count", 1)
        if isinstance(count, bool) or not isinstance(count, int):
            return None
        return {"type": "backspace", "count": max(1, min(count, MAX_BACKSPACE_COUNT))}
    elif msg_type in ("enter", "auth"):
        return msg
    return None


def check_auth(msg, token: str) -> bool:
    """Check whether an auth message carries the expected token."""
    if not isinstance(msg, dict) or msg.get("type") != "auth":
        return False
    supplied = msg.get("token")
    if not isinstance(supplied, str):
        return False
    return hmac.compare_digest(supplied, token)


def process_message(msg: dict, mode: str, interval: float) -> tuple[str, str]:
    """
    Process a single sanitized message (runs in thread pool).
    Returns (message_type, description) for logging.
    """
    msg_type = msg.get("type", "unknown")

    if msg_type == "text":
        content = msg.get("content", "")
        if content:
            handle_text(content, mode, interval)
        return ("text", f"TYPING: '{content}'")
    elif msg_type == "backspace":
        count = msg.get("count", 1)
        handle_backspace(count, interval)
        return ("backspace", f"BACKSPACE: x{count}")
    elif msg_type == "enter":
        handle_enter()
        return ("enter", "ENTER")
    else:
        return ("unknown", f"Unknown: {msg}")


class AirTypeServer:
    """WebSocket server that receives typing commands from Android."""

    def __init__(
        self,
        port: int = 8765,
        mode: str = "ascii",
        interval: float = 0.01,
        token: str = "",
        on_connect: Optional[Callable[[str], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        on_message: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.port = port
        self.mode = mode
        self.interval = interval
        self.token = token
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_message = on_message
        self.on_error = on_error

        self.message_queue: Optional[asyncio.Queue] = None
        self.server: Optional[websockets.WebSocketServer] = None
        self.is_running = False
        self._stop_event: Optional[asyncio.Event] = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def start(self):
        """Start the WebSocket server."""
        self.is_running = True
        self.message_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self._stop_event = asyncio.Event()

        # Start queue processor
        processor_task = asyncio.create_task(self._queue_processor())

        try:
            self.server = await websockets.serve(
                self._handle_client,
                "0.0.0.0",
                self.port
            )
            logger.info(f"Server listening on 0.0.0.0:{self.port}")

            # Wait until stopped
            await self._stop_event.wait()

        finally:
            self.is_running = False
            processor_task.cancel()
            if self.server:
                self.server.close()
                try:
                    await asyncio.wait_for(self.server.wait_closed(), timeout=5)
                except asyncio.TimeoutError:
                    logger.warning("Timed out waiting for server to close")
            self._executor.shutdown(wait=False)

    def stop(self):
        """Signal the server to stop."""
        if self._stop_event:
            self._stop_event.set()

    async def _authenticate(self, websocket, client_ip: str) -> bool:
        """
        Require a valid auth message as the first frame when a token is set.
        Returns True if the client may proceed.
        """
        if not self.token:
            return True

        try:
            first = await asyncio.wait_for(websocket.recv(), timeout=AUTH_TIMEOUT_SECONDS)
            msg = json.loads(first)
        except (asyncio.TimeoutError, json.JSONDecodeError,
                websockets.exceptions.ConnectionClosed):
            msg = None

        if msg is not None and check_auth(msg, self.token):
            await websocket.send(json.dumps({"type": "auth_ok"}))
            return True

        logger.warning(f"Rejected client {client_ip}: authentication failed")
        if self.on_error:
            self.on_error(f"Rejected {client_ip}: authentication failed")
        await websocket.close(CLOSE_CODE_AUTH_FAILED, "authentication failed")
        return False

    async def _handle_client(self, websocket):
        """Handle incoming WebSocket connections."""
        client_ip = websocket.remote_address[0]

        try:
            if not await self._authenticate(websocket, client_ip):
                return
        except websockets.exceptions.ConnectionClosed:
            return

        logger.info(f"Client connected from {client_ip}")

        if self.on_connect:
            self.on_connect(client_ip)

        try:
            async for message in websocket:
                try:
                    msg = sanitize_message(json.loads(message))
                    if msg is None or msg["type"] == "auth":
                        logger.warning(f"Ignoring malformed/unexpected message from {client_ip}")
                        continue
                    self.message_queue.put_nowait(msg)
                    logger.debug(f"Queued: {msg} (queue size: {self.message_queue.qsize()})")
                except asyncio.QueueFull:
                    logger.warning("Message queue full, dropping message")
                    if self.on_error:
                        self.on_error("Message queue full, dropping message")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON: {message}")
                    if self.on_error:
                        self.on_error(f"Invalid JSON: {message}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Client {client_ip} disconnected: {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"Error handling client {client_ip}: {e}")
            if self.on_error:
                self.on_error(str(e))
        finally:
            if self.on_disconnect:
                self.on_disconnect(client_ip)

    async def _queue_processor(self):
        """Process messages from the queue sequentially."""
        loop = asyncio.get_event_loop()

        while True:
            msg = await self.message_queue.get()
            try:
                _, description = await loop.run_in_executor(
                    self._executor,
                    process_message,
                    msg,
                    self.mode,
                    self.interval,
                )
                logger.info(description)
                if self.on_message:
                    self.on_message(description)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                if self.on_error:
                    self.on_error(str(e))
            finally:
                self.message_queue.task_done()
