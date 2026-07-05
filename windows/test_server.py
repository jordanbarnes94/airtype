"""
Unit tests for the AirType server's message handling.

pyautogui and pyperclip are mocked out (they need a display / Windows),
so these tests run headless on any platform: `pytest windows/`.
"""

import asyncio
import json
import sys
from unittest.mock import MagicMock

# Must be stubbed before importing server: pyautogui requires a display at import time
sys.modules.setdefault("pyautogui", MagicMock())
sys.modules.setdefault("pyperclip", MagicMock())

import pytest
import websockets

import server
from server import (
    MAX_BACKSPACE_COUNT,
    MAX_TEXT_LENGTH,
    check_auth,
    process_message,
    sanitize_message,
)


@pytest.fixture(autouse=True)
def reset_pyautogui():
    server.pyautogui.reset_mock()
    yield


class TestSanitizeMessage:
    def test_valid_text(self):
        assert sanitize_message({"type": "text", "content": "hello"}) == {
            "type": "text",
            "content": "hello",
        }

    def test_text_missing_content_defaults_to_empty(self):
        assert sanitize_message({"type": "text"}) == {"type": "text", "content": ""}

    def test_text_with_non_string_content_rejected(self):
        assert sanitize_message({"type": "text", "content": 42}) is None
        assert sanitize_message({"type": "text", "content": ["a"]}) is None

    def test_oversized_text_truncated(self):
        msg = sanitize_message({"type": "text", "content": "x" * (MAX_TEXT_LENGTH + 100)})
        assert len(msg["content"]) == MAX_TEXT_LENGTH

    def test_valid_backspace(self):
        assert sanitize_message({"type": "backspace", "count": 3}) == {
            "type": "backspace",
            "count": 3,
        }

    def test_backspace_count_defaults_to_one(self):
        assert sanitize_message({"type": "backspace"}) == {"type": "backspace", "count": 1}

    def test_backspace_count_clamped(self):
        assert sanitize_message({"type": "backspace", "count": 10**9})["count"] == MAX_BACKSPACE_COUNT
        assert sanitize_message({"type": "backspace", "count": -5})["count"] == 1
        assert sanitize_message({"type": "backspace", "count": 0})["count"] == 1

    def test_backspace_non_int_count_rejected(self):
        assert sanitize_message({"type": "backspace", "count": "99"}) is None
        assert sanitize_message({"type": "backspace", "count": 1.5}) is None
        assert sanitize_message({"type": "backspace", "count": True}) is None

    def test_enter_passthrough(self):
        assert sanitize_message({"type": "enter"}) == {"type": "enter"}

    def test_auth_passthrough(self):
        msg = {"type": "auth", "token": "ABC123"}
        assert sanitize_message(msg) == msg

    def test_non_dict_rejected(self):
        assert sanitize_message("just a string") is None
        assert sanitize_message([1, 2, 3]) is None
        assert sanitize_message(None) is None
        assert sanitize_message(42) is None

    def test_unknown_type_rejected(self):
        assert sanitize_message({"type": "shutdown"}) is None
        assert sanitize_message({}) is None


class TestCheckAuth:
    def test_correct_token(self):
        assert check_auth({"type": "auth", "token": "SECRET"}, "SECRET")

    def test_wrong_token(self):
        assert not check_auth({"type": "auth", "token": "WRONG"}, "SECRET")

    def test_missing_token(self):
        assert not check_auth({"type": "auth"}, "SECRET")

    def test_non_string_token(self):
        assert not check_auth({"type": "auth", "token": 123}, "SECRET")

    def test_wrong_message_type(self):
        assert not check_auth({"type": "text", "token": "SECRET"}, "SECRET")

    def test_non_dict(self):
        assert not check_auth("auth", "SECRET")


class TestProcessMessage:
    def test_text_ascii_mode_types_content(self):
        msg_type, desc = process_message(
            {"type": "text", "content": "hi"}, "ascii", 0.01
        )
        assert msg_type == "text"
        assert "hi" in desc
        server.pyautogui.write.assert_called_once_with("hi", interval=0.01)

    def test_empty_text_does_not_type(self):
        process_message({"type": "text", "content": ""}, "ascii", 0.01)
        server.pyautogui.write.assert_not_called()

    def test_backspace_presses_key(self):
        msg_type, _ = process_message({"type": "backspace", "count": 4}, "ascii", 0.01)
        assert msg_type == "backspace"
        server.pyautogui.press.assert_called_once_with(
            "backspace", presses=4, interval=0.01
        )

    def test_enter_presses_key(self):
        msg_type, _ = process_message({"type": "enter"}, "ascii", 0.01)
        assert msg_type == "enter"
        server.pyautogui.press.assert_called_once_with("enter")

    def test_unknown_type_is_noop(self):
        msg_type, _ = process_message({"type": "bogus"}, "ascii", 0.01)
        assert msg_type == "unknown"
        server.pyautogui.write.assert_not_called()
        server.pyautogui.press.assert_not_called()

    def test_text_unicode_mode_uses_clipboard(self):
        process_message({"type": "text", "content": "héllo"}, "unicode", 0.01)
        server.pyautogui.hotkey.assert_called_once_with("ctrl", "v")
        server.pyautogui.write.assert_not_called()


async def _wait_for_call(mock, timeout=5.0):
    """Wait until a mock has been called (send() returns before the server
    has received, let alone processed, the frame)."""
    for _ in range(int(timeout / 0.01)):
        if mock.call_count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"{mock} was not called within {timeout}s")


async def _start_server(srv):
    """Start srv on an ephemeral port; returns (task, actual_port)."""
    task = asyncio.create_task(srv.start())
    for _ in range(200):
        if srv.server is not None:
            break
        await asyncio.sleep(0.01)
    assert srv.server is not None, "server did not start"
    port = srv.server.sockets[0].getsockname()[1]
    return task, port


class TestAuthHandshake:
    def test_wrong_token_rejected(self):
        async def run():
            srv = server.AirTypeServer(port=0, token="SECRET")
            task, port = await _start_server(srv)
            try:
                async with websockets.connect(f"ws://127.0.0.1:{port}") as conn:
                    await conn.send(json.dumps({"type": "auth", "token": "WRONG"}))
                    with pytest.raises(websockets.exceptions.ConnectionClosed):
                        await asyncio.wait_for(conn.recv(), timeout=5)
                    assert conn.close_code == server.CLOSE_CODE_AUTH_FAILED
            finally:
                srv.stop()
                await task

        asyncio.run(run())

    def test_correct_token_accepted(self):
        async def run():
            srv = server.AirTypeServer(port=0, token="SECRET")
            task, port = await _start_server(srv)
            try:
                async with websockets.connect(f"ws://127.0.0.1:{port}") as conn:
                    await conn.send(json.dumps({"type": "auth", "token": "SECRET"}))
                    reply = json.loads(await asyncio.wait_for(conn.recv(), timeout=5))
                    assert reply == {"type": "auth_ok"}

                    # And typing flows through after auth
                    await conn.send(json.dumps({"type": "text", "content": "hi"}))
                    await _wait_for_call(server.pyautogui.write)
                    server.pyautogui.write.assert_called_once_with("hi", interval=srv.interval)
            finally:
                srv.stop()
                await task

        asyncio.run(run())

    def test_no_token_means_no_auth_required(self):
        async def run():
            srv = server.AirTypeServer(port=0)
            task, port = await _start_server(srv)
            try:
                async with websockets.connect(f"ws://127.0.0.1:{port}") as conn:
                    await conn.send(json.dumps({"type": "text", "content": "open"}))
                    await _wait_for_call(server.pyautogui.write)
                    server.pyautogui.write.assert_called_once_with("open", interval=srv.interval)
            finally:
                srv.stop()
                await task

        asyncio.run(run())
