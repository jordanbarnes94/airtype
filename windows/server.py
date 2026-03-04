#!/usr/bin/env python3
"""
AirType - Core Server Logic
Shared between CLI (main.py) and GUI (gui.py)
"""

import asyncio
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


def process_message(msg: dict, mode: str, interval: float) -> tuple[str, str]:
    """
    Process a single message (runs in thread pool).
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
        on_connect: Optional[Callable[[str], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        on_message: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.port = port
        self.mode = mode
        self.interval = interval
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
        self.message_queue = asyncio.Queue()
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
                await self.server.wait_closed()

    def stop(self):
        """Signal the server to stop."""
        if self._stop_event:
            self._stop_event.set()

    async def _handle_client(self, websocket):
        """Handle incoming WebSocket connections."""
        client_ip = websocket.remote_address[0]
        logger.info(f"Client connected from {client_ip}")

        if self.on_connect:
            self.on_connect(client_ip)

        try:
            async for message in websocket:
                try:
                    msg = json.loads(message)
                    await self.message_queue.put(msg)
                    logger.debug(f"Queued: {msg} (queue size: {self.message_queue.qsize()})")
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
                msg_type, description = await loop.run_in_executor(
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
