"""
Unit tests for CardKB sticky Ctrl modifier latch on Whiskerframe terminal bridge.

Tests the state machine implemented in pi/terminal/bridge.py:
- Chord: Fn+Tab (0x8C / 140)
- Single-key latch: arms for exactly one key, sends `char & 0x1F`
- Toggle cancel: second press of chord disarms
- Passthrough cancel: non-qualifying key cancels and passes through
- Timeout: disarms after 3.0s window
- Cursor indication: recolored when armed
- Login screen: chord is ignored
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from terminal.bridge import (  # noqa: E402
    CTRL_LATCH_CHORD,
    CTRL_LATCH_CHORDS,
    CTRL_LATCH_TIMEOUT_S,
    KeyQueue,
    TerminalBridge,
    _ShellSession,
)
from terminal.login import LoginScreen, LoginState  # noqa: E402
from terminal.theme import load_theme  # noqa: E402

from whiskerframe.terminal import TerminalGeometry  # noqa: E402


class TestCtrlLatch(unittest.TestCase):
    """Test suite for CardKB sticky Ctrl modifier latch."""

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.geometry = TerminalGeometry.for_font_size(2)
        self.mock_bridge = MagicMock(spec=TerminalBridge)
        self.mock_bridge._theme = self.theme
        self.mock_bridge._geometry = self.geometry
        self.mock_bridge._paint = MagicMock()
        self.mock_bridge._rebuild_geometry = MagicMock()

        self.key_queue = KeyQueue(iter([]))
        # Mock master_fd
        self.master_fd = 999
        self.session = _ShellSession(self.mock_bridge, self.master_fd, self.key_queue)

    def test_chord_definition(self) -> None:
        """Verify latch chord is Fn+Tab (0x8C / 140)."""
        self.assertEqual(CTRL_LATCH_CHORD, 0x8C)
        self.assertIn(0x8C, CTRL_LATCH_CHORDS)
        self.assertEqual(CTRL_LATCH_TIMEOUT_S, 3.0)

    @patch("os.write")
    def test_single_key_ctrl_latch(self, mock_write: MagicMock) -> None:
        """Pressing latch chord then 'c' emits Ctrl-C (0x03) and disarms."""
        # Step 1: Arm latch with Fn+Tab (0x8C)
        handled = self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(handled)
        self.assertTrue(self.session._is_ctrl_armed())
        mock_write.assert_not_called()

        # Step 2: Next letter 'c' (0x63)
        handled = self.session._process_single_key(ord("c"))
        self.assertTrue(handled)
        mock_write.assert_called_once_with(self.master_fd, b"\x03")
        self.assertFalse(self.session._is_ctrl_armed())

        # Step 3: Subsequent key 'c' is NOT modified
        mock_write.reset_mock()
        self.session._process_single_key(ord("c"))
        mock_write.assert_called_once_with(self.master_fd, b"c")

    @patch("os.write")
    def test_ctrl_d_and_ctrl_z(self, mock_write: MagicMock) -> None:
        """Test Ctrl-D (0x04) and Ctrl-Z (0x1A) generation."""
        # Ctrl-D
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.session._process_single_key(ord("d"))
        mock_write.assert_called_with(self.master_fd, b"\x04")

        # Ctrl-Z (uppercase letter test)
        mock_write.reset_mock()
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.session._process_single_key(ord("Z"))
        mock_write.assert_called_with(self.master_fd, b"\x1a")

    @patch("os.write")
    def test_extended_ctrl_characters(self, mock_write: MagicMock) -> None:
        r"""Test @, [, \, ], ^, _, space with Ctrl latch."""
        chars_expected = [
            (ord("@"), b"\x00"),
            (ord("["), b"\x1b"),
            (ord("\\"), b"\x1c"),
            (ord("]"), b"\x1d"),
            (ord("^"), b"\x1e"),
            (ord("_"), b"\x1f"),
            (ord(" "), b"\x00"),
        ]
        for key_int, expected_bytes in chars_expected:
            mock_write.reset_mock()
            self.session._process_single_key(CTRL_LATCH_CHORD)
            self.session._process_single_key(key_int)
            mock_write.assert_called_once_with(self.master_fd, expected_bytes)
            self.assertFalse(self.session._is_ctrl_armed())

    @patch("os.write")
    def test_toggle_cancel(self, mock_write: MagicMock) -> None:
        """Pressing latch chord a second time disarms without emitting bytes."""
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())

        # Toggle off
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertFalse(self.session._is_ctrl_armed())
        mock_write.assert_not_called()

        # Next key is normal
        self.session._process_single_key(ord("c"))
        mock_write.assert_called_once_with(self.master_fd, b"c")

    @patch("os.write")
    def test_non_matching_key_cancels_and_passes_through(
        self,
        mock_write: MagicMock,
    ) -> None:
        """Non-qualifying key (e.g. number '1') cancels latch and passes through."""
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())

        # Press '1' (0x31)
        self.session._process_single_key(ord("1"))
        self.assertFalse(self.session._is_ctrl_armed())
        mock_write.assert_called_once_with(self.master_fd, b"1")

    @patch("os.write")
    def test_arrow_cancels_and_passes_through(self, mock_write: MagicMock) -> None:
        """Arrow key cancels latch and passes escape sequence."""
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())

        # Down arrow (0xB6)
        self.session._process_single_key(0xB6)
        self.assertFalse(self.session._is_ctrl_armed())
        mock_write.assert_called_once_with(self.master_fd, b"\x1b[B")

    def test_timeout_expiration(self) -> None:
        """Latch expires after 3.0 seconds."""
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())

        # Simulate time passing > 3.0s
        self.session._ctrl_armed_at -= 3.1
        self.assertFalse(self.session._is_ctrl_armed())

    def test_cursor_recoloring_when_armed(self) -> None:
        """Cursor cell uses theme.ansi[11] when armed, theme.cursor when normal."""
        # Unarmed
        self.assertFalse(self.session._is_ctrl_armed())
        self.session._paint_session()
        unarmed_grid = self.mock_bridge._paint.call_args[0][0]
        # Armed
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        armed_grid = self.mock_bridge._paint.call_args[0][0]

        # The cursor background cell at (cursor_row, cursor_col) should differ between armed and unarmed
        unarmed_cursor_bg = unarmed_grid.cell_at(
            unarmed_grid.cursor_row,
            unarmed_grid.cursor_col,
        ).bg
        armed_cursor_bg = armed_grid.cell_at(
            armed_grid.cursor_row,
            armed_grid.cursor_col,
        ).bg
        self.assertEqual(unarmed_cursor_bg, self.theme.cursor)
        self.assertEqual(armed_cursor_bg, self.theme.ansi[11])
        self.assertNotEqual(unarmed_cursor_bg, armed_cursor_bg)

    def test_ignored_on_login_screen(self) -> None:
        """CTRL_LATCH_CHORD is completely dropped by the login screen."""
        bridge = TerminalBridge.__new__(TerminalBridge)
        state = LoginState(["root", "neko", "guest"])
        # In user select screen
        self.assertEqual(state.screen, LoginScreen.USER_SELECT)
        result = bridge._process_login_key(state, CTRL_LATCH_CHORD)
        self.assertIsNone(result)
        # Selection and screen remain unchanged
        self.assertEqual(state.screen, LoginScreen.USER_SELECT)
        self.assertEqual(state.selected, 0)


if __name__ == "__main__":
    unittest.main()
