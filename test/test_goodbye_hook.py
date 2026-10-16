#!/usr/bin/env python3
"""
Unit tests for Cyberdeck goodbye splash hook (pi/bin/goodbye_hook).

Validates:
- Image blob validation (128x128x2 = 32768 bytes).
- Centered geometry calculation (x=96, y=56 on 320x240 screen).
- Sequence: theme background clear -> DrawImage chunks -> hold -> black wipe.
- Fail-silent behavior on missing serial device, read error, or timeout.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

_HOOK_PATH = REPO_ROOT / "pi/bin/goodbye_hook"
_loader = SourceFileLoader("goodbye_hook", str(_HOOK_PATH))
_spec = importlib.util.spec_from_loader("goodbye_hook", _loader)
if _spec is None:
    raise ImportError(f"Cannot load goodbye_hook from {_HOOK_PATH}")
goodbye_hook = importlib.util.module_from_spec(_spec)
sys.modules["goodbye_hook"] = goodbye_hook
_loader.exec_module(goodbye_hook)

from whiskerframe.models import DrawRect, DrawText  # noqa: E402
from whiskerframe.protocol import decode  # noqa: E402
from whiskerframe.terminal import (  # noqa: E402
    DISPLAY_WIDTH,
    DisplaySleep,
    DrawImage,
)


class TestGoodbyeHook(unittest.TestCase):
    """Test suite for goodbye splash hook."""

    def setUp(self) -> None:
        self.tmp_dir = REPO_ROOT / "test/__pycache__/goodbye_test_tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.valid_blob_path = self.tmp_dir / "valid.rgb565"
        self.valid_bytes = bytes([0x18, 0xC5] * (128 * 128))
        self.valid_blob_path.write_bytes(self.valid_bytes)

    def tearDown(self) -> None:
        if self.valid_blob_path.exists():
            self.valid_blob_path.unlink()
        if self.tmp_dir.exists():
            self.tmp_dir.rmdir()

    def test_read_image_blob_valid(self) -> None:
        """Valid 32768-byte file is read correctly."""
        blob = goodbye_hook._read_image_blob(self.valid_blob_path)
        self.assertIsNotNone(blob)
        self.assertEqual(len(blob), 32768)

    def test_read_image_blob_invalid_size(self) -> None:
        """Short or oversized file returns None."""
        bad_path = self.tmp_dir / "bad.rgb565"
        bad_path.write_bytes(b"too short")
        self.assertIsNone(goodbye_hook._read_image_blob(bad_path))
        bad_path.unlink()

    def test_read_image_blob_missing(self) -> None:
        """Missing file returns None without raising."""
        missing_path = self.tmp_dir / "nonexistent.rgb565"
        self.assertIsNone(goodbye_hook._read_image_blob(missing_path))

    def test_stream_image_chunks_coordinates(self) -> None:
        """Image is centered horizontally at x=96, y=36 on 320x240 display."""
        mock_ser = MagicMock()
        written_frames: list[bytes] = []
        mock_ser.write.side_effect = written_frames.append

        import time

        goodbye_hook._stream_image_chunks(
            mock_ser,
            self.valid_bytes,
            start_time=time.monotonic(),
            y_pos=36,
        )
        self.assertTrue(len(written_frames) > 0)

        # Decode first chunk
        first_cmd = decode(written_frames[0])
        self.assertIsInstance(first_cmd, DrawImage)
        self.assertEqual(first_cmd.x, (DISPLAY_WIDTH - 128) // 2)  # 96
        self.assertEqual(first_cmd.y, 36)
        self.assertEqual(first_cmd.w, 128)
        self.assertEqual(first_cmd.h, goodbye_hook._CHUNK_ROWS)

    @patch("time.sleep")
    def test_full_send_goodbye_shutdown_sequence(self, mock_sleep: MagicMock) -> None:
        """Shutdown sequence transmits clear, image, 'bai baiii!', hold, black wipe, and sleep."""
        mock_ser = MagicMock()
        written_frames: list[bytes] = []
        mock_ser.write.side_effect = written_frames.append

        with patch("serial.Serial", return_value=mock_ser):
            goodbye_hook.send_goodbye(
                port="/dev/test_port",
                rgb565_path=self.valid_blob_path,
                mode="shutdown",
                hold_s=1.0,
            )

        self.assertEqual(mock_sleep.call_count, 2)
        mock_ser.close.assert_called_once()

        # Check first frame (clear to theme bg)
        first_cmd = decode(written_frames[0])
        self.assertIsInstance(first_cmd, DrawRect)
        self.assertEqual(first_cmd.color, goodbye_hook._THEME_BG)

        # Check second frame (subtitle text rendered before image streaming)
        second_cmd = decode(written_frames[1])
        self.assertIsInstance(second_cmd, DrawText)
        self.assertEqual(second_cmd.text, "bai baiii!")
        self.assertEqual(second_cmd.x, 160)
        self.assertEqual(second_cmd.y, 184)

        # Check third frame (image chunks start after text)
        third_cmd = decode(written_frames[2])
        self.assertIsInstance(third_cmd, DrawImage)

        # Check subtitle text frame in written frames
        text_frames = [
            cmd for f in written_frames if isinstance((cmd := decode(f)), DrawText)
        ]
        self.assertEqual(len(text_frames), 1)
        self.assertEqual(text_frames[0].text, "bai baiii!")
        self.assertEqual(text_frames[0].x, 160)
        self.assertEqual(text_frames[0].y, 184)

        # Check last frames (wipe to black + DisplaySleep)
        second_last_cmd = decode(written_frames[-2])
        self.assertIsInstance(second_last_cmd, DrawRect)
        self.assertEqual(second_last_cmd.color, goodbye_hook._BLACK)

        last_cmd = decode(written_frames[-1])
        self.assertIsInstance(last_cmd, DisplaySleep)

    @patch("time.sleep")
    def test_full_send_goodbye_reboot_sequence(self, mock_sleep: MagicMock) -> None:
        """Reboot sequence transmits clear, image, 'brb :3', hold, without black wipe or sleep."""
        mock_ser = MagicMock()
        written_frames: list[bytes] = []
        mock_ser.write.side_effect = written_frames.append

        with patch("serial.Serial", return_value=mock_ser):
            goodbye_hook.send_goodbye(
                port="/dev/test_port",
                rgb565_path=self.valid_blob_path,
                mode="reboot",
                hold_s=1.0,
            )

        mock_sleep.assert_called_once()
        mock_ser.close.assert_called_once()

        # Check first frame (clear to theme bg)
        first_cmd = decode(written_frames[0])
        self.assertIsInstance(first_cmd, DrawRect)
        self.assertEqual(first_cmd.color, goodbye_hook._THEME_BG)

        # Check second frame (subtitle text rendered before image streaming)
        second_cmd = decode(written_frames[1])
        self.assertIsInstance(second_cmd, DrawText)
        self.assertEqual(second_cmd.text, "brb :3")
        self.assertEqual(second_cmd.x, 160)
        self.assertEqual(second_cmd.y, 184)

        # Check third frame (image chunks start after text)
        third_cmd = decode(written_frames[2])
        self.assertIsInstance(third_cmd, DrawImage)

        # Check subtitle text frame
        text_frames = [
            cmd for f in written_frames if isinstance((cmd := decode(f)), DrawText)
        ]
        self.assertEqual(len(text_frames), 1)
        self.assertEqual(text_frames[0].text, "brb :3")
        self.assertEqual(text_frames[0].x, 160)
        self.assertEqual(text_frames[0].y, 184)

        # Reboot does NOT send black wipe or sleep (keeps 'brb :3' on screen until reboot completes)
        black_frames = [
            cmd
            for f in written_frames
            if isinstance((cmd := decode(f)), DrawRect)
            and cmd.color == goodbye_hook._BLACK
        ]
        self.assertEqual(len(black_frames), 0)
        sleep_frames = [
            cmd for f in written_frames if isinstance((cmd := decode(f)), DisplaySleep)
        ]
        self.assertEqual(len(sleep_frames), 0)

    def test_fail_silent_on_missing_serial_port(self) -> None:
        """send_goodbye fails silent when serial port cannot be opened."""
        with patch("serial.Serial", side_effect=OSError("Device not found")):
            # Must not raise
            goodbye_hook.send_goodbye(
                port="/dev/nonexistent",
                rgb565_path=self.valid_blob_path,
                hold_s=0.5,
            )


if __name__ == "__main__":
    unittest.main()
