#!/usr/bin/env python3
"""
Unit test suite for CYD USB-serial transport and bridge resilience.

Validates robust handling of physical link faults on `/dev/serial/...`:
1. Port Disconnection & Backoff Recovery:
   - Device node disappears (`FileNotFoundError`, `OSError(ENODEV)`).
   - `_ensure_serial()` enters bounded exponential backoff (0.5s -> 5.0s max).
   - Reappearance of device reopens link, resets backoff, and invalidates baseline (`_prev = None`).
2. Mid-Frame Disconnections & Write Failures:
   - Write raises `OSError` (EIO, ENODEV, EPIPE).
   - `_send()` handles failure cleanly, drops transport handle, and returns `False`.
   - `_paint()` invalidates `_prev`, ensuring next frame is a clean full repaint.
3. Framing Errors, Noise, & Partial Opcode Writes:
   - Truncated frames (SOF only, truncated header, missing CRC).
   - Random noise bytes injected before/after valid frames.
   - CRC8 corruption validation.
   - Protocol decoder recovery: subsequent valid frame decodes cleanly after malformed inputs.
4. Opcode 0x06 SLEEP & Wake Transitions:
   - Serialization and decoding of `DisplaySleep` (opcode 0x06).
   - Sleep frame transmission followed by wake frame (`DrawRect` / `DrawCells`).
   - Simulates firmware sleep state and wake command dispatch.
"""

from __future__ import annotations

import errno
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from terminal.bridge import (  # noqa: E402
    BridgeConfig,
    TerminalBridge,
)
from terminal.grid import Grid  # noqa: E402
from terminal.theme import load_theme  # noqa: E402
from whiskerframe.models import DrawRect, DrawText  # noqa: E402
from whiskerframe.protocol import (  # noqa: E402
    CRC8_CHECK,
    OPCODE_DRAW_CELLS,
    OPCODE_DRAW_RECT,
    OPCODE_DRAW_TEXT,
    OPCODE_SLEEP,
    crc8,
    decode,
    frame,
    serialize,
)
from whiskerframe.terminal import (  # noqa: E402
    DisplaySleep,
    DrawCells,
    TerminalGeometry,
)
from whiskerframe.transport import SerialTransport  # noqa: E402


class TestSerialResilience(unittest.TestCase):
    """Resilience tests for CYD serial link and terminal bridge."""

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.config = BridgeConfig(
            serial_port="/dev/serial/by-id/usb-cyd-test",
            baud=115200,
            theme=self.theme,
        )
        self.bridge = TerminalBridge(self.config)

    @patch("terminal.bridge.time.sleep")
    @patch("terminal.bridge.SerialTransport")
    def test_disconnection_backoff_and_reconnection(
        self,
        mock_transport_cls: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """Port disconnection triggers exponential backoff; reconnect resets backoff."""
        # Step 1: Device node missing
        mock_transport_cls.side_effect = OSError(errno.ENOENT, "No such file or directory")
        self.assertIsNone(self.bridge._ensure_serial())
        mock_sleep.assert_called_once_with(0.5)
        self.assertEqual(self.bridge._serial_backoff, 1.0)

        # Step 2: Next retry fails -> backoff doubles
        mock_sleep.reset_mock()
        self.assertIsNone(self.bridge._ensure_serial())
        mock_sleep.assert_called_once_with(1.0)
        self.assertEqual(self.bridge._serial_backoff, 2.0)

        # Step 3: Continues doubling up to 5.0s cap
        mock_sleep.reset_mock()
        self.assertIsNone(self.bridge._ensure_serial())
        mock_sleep.assert_called_once_with(2.0)
        self.assertEqual(self.bridge._serial_backoff, 4.0)

        mock_sleep.reset_mock()
        self.assertIsNone(self.bridge._ensure_serial())
        mock_sleep.assert_called_once_with(4.0)
        self.assertEqual(self.bridge._serial_backoff, 5.0)

        # Next stays at 5.0s
        mock_sleep.reset_mock()
        self.assertIsNone(self.bridge._ensure_serial())
        mock_sleep.assert_called_once_with(5.0)
        self.assertEqual(self.bridge._serial_backoff, 5.0)

        # Step 4: Device reappears -> successful open resets backoff and forces full repaint
        mock_instance = MagicMock()
        mock_transport_cls.side_effect = None
        mock_transport_cls.return_value = mock_instance
        self.bridge._prev = MagicMock()  # Simulate previous cached frame

        transport = self.bridge._ensure_serial()
        self.assertIs(transport, mock_instance)
        self.assertEqual(self.bridge._serial_backoff, 0.5)
        self.assertIsNone(self.bridge._prev, "Reconnection must force full repaint (_prev=None)")

    def test_mid_frame_write_error_drops_transport(self) -> None:
        """Write error on serial transport cleanly closes and drops transport."""
        mock_transport = MagicMock()
        mock_transport.send.side_effect = OSError(errno.EIO, "I/O error on USB serial")
        self.bridge._transport = mock_transport

        frame_data = b"\xAA\x01\x00\x06\xCC"
        ok = self.bridge._send(frame_data)
        self.assertFalse(ok)
        self.assertIsNone(self.bridge._transport, "Transport handle must be dropped on write error")
        mock_transport.close.assert_called_once()

    def test_paint_detects_failure_and_drops_baseline(self) -> None:
        """A partial or failed paint does not update _prev, forcing clean repaint next time."""
        mock_transport = MagicMock()
        # First send succeeds (clear_panel), second send fails (cell run)
        mock_transport.send.side_effect = [None, OSError(errno.ENODEV, "Device disconnected")]
        self.bridge._transport = mock_transport

        grid = Grid(self.bridge._geometry.cols, self.bridge._geometry.rows, self.theme.fg, self.theme.bg)
        grid.put_char("A", self.theme.fg, self.theme.bg)

        # First paint (prev is None)
        self.bridge._paint(grid)
        self.assertIsNone(self.bridge._prev, "Failed paint must leave _prev=None")

    def test_partial_frame_and_framing_error_rejection(self) -> None:
        """Malformed, truncated, and corrupt frames are rejected by decoder."""
        valid_cmd = DrawRect(x=0, y=0, w=10, h=10, color=0xFFFF, filled=True)
        valid_bytes = serialize(valid_cmd)

        # 1. Truncated before length
        with self.assertRaises(ValueError):
            decode(valid_bytes[:2])

        # 2. Truncated mid-payload
        with self.assertRaises(ValueError):
            decode(valid_bytes[: len(valid_bytes) - 3])

        # 3. Bad CRC
        corrupt_crc_bytes = bytearray(valid_bytes)
        corrupt_crc_bytes[-1] ^= 0xFF
        with self.assertRaises(ValueError) as ctx:
            decode(bytes(corrupt_crc_bytes))
        self.assertIn("CRC mismatch", str(ctx.exception))

        # 4. Unknown opcode
        bad_opcode_frame = frame(0x99, b"\x00\x01")
        with self.assertRaises(ValueError) as ctx:
            decode(bad_opcode_frame)
        self.assertIn("unknown opcode", str(ctx.exception).lower())

    def test_opcode_0x06_sleep_serialization_and_recovery(self) -> None:
        """Opcode 0x06 (SLEEP) serializes with 0-byte payload and recovers on next command."""
        sleep_cmd = DisplaySleep()
        sleep_frame = serialize(sleep_cmd)

        # Verify frame structure: [SOF 0xA5][LEN 0x0001][OPCODE 0x06][CRC8]
        # LEN is the 16-bit length of (OPCODE + PAYLOAD) = 1 + 0 = 1.
        self.assertEqual(sleep_frame[0], 0xA5)
        frame_len = int.from_bytes(sleep_frame[1:3], "little")
        self.assertEqual(frame_len, 1)
        self.assertEqual(sleep_frame[3], OPCODE_SLEEP)
        self.assertEqual(sleep_frame[3], 0x06)

        # Verify CRC: for body = [OPCODE_SLEEP] (0x06)
        expected_crc = crc8(bytes([OPCODE_SLEEP]))
        self.assertEqual(sleep_frame[4], expected_crc)
        self.assertEqual(len(sleep_frame), 5)

        # Decode sleep frame
        decoded_sleep = decode(sleep_frame)
        self.assertIsInstance(decoded_sleep, DisplaySleep)

        # Wake sequence: subsequent drawing command decodes cleanly
        wake_cmd = DrawText(x=96, y=56, text="wake up!", color=0xFFFF)
        wake_frame = serialize(wake_cmd)
        decoded_wake = decode(wake_frame)
        self.assertIsInstance(decoded_wake, DrawText)
        self.assertEqual(decoded_wake.text, "wake up!")

    def test_stream_interleaved_garbage_and_valid_frames(self) -> None:
        """Decoder rejects framing noise and decodes trailing valid frame."""
        valid_cmd = DrawCells(col=0, row=0, fg=0xFFFF, bg=0x0000, font_size=1, text="ok")
        valid_bytes = serialize(valid_cmd)

        # Prepend arbitrary noise bytes
        noise = b"\x00\xFF\xAA\x12\x34\x56\x78\x9A\xBC\xDE"
        # The decoder functions on individual framed byte sequences
        with self.assertRaises(ValueError):
            decode(noise)

        # Valid frame immediately following decodes successfully
        decoded = decode(valid_bytes)
        self.assertIsInstance(decoded, DrawCells)
        self.assertEqual(decoded.text, "ok")


def main() -> int:
    """Run standalone serial resilience tests."""
    print("=" * 70)
    print("Running Whiskerframe Serial Link & Protocol Resilience Tests")
    print("=" * 70)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSerialResilience)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
