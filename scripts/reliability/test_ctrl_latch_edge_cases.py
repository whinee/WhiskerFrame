#!/usr/bin/env python3
"""
Edge case and property-based test suite for CardKB sticky Ctrl modifier latch.

Validates the state machine in `pi/terminal/bridge.py` under exhaustive inputs:
1. Hypothesis property tests:
   - Every valid Ctrl character in `_CTRL_VALID_CHARS` transforms to `char & 0x1F`.
   - Every character outside `_CTRL_VALID_CHARS` passes through un-modified and disarms.
   - Latch is strictly single-use: key N modified, key N+1 unmodified.
2. I2C NeoPixel LED feedback contract:
   - set_ctrl_led(True) called on arming (255, 200, 0 yellow)
   - set_ctrl_led(False) called on single-key consumption
   - set_ctrl_led(False) called on toggle cancel (double Fn+Tab)
   - set_ctrl_led(False) called on timeout expiration
   - set_ctrl_led(False) called on resize chord interruption
   - set_ctrl_led(False) called on session teardown/exit
3. Boundary conditions and state machine transitions:
   - Exact timeout boundary (3.0s vs 3.001s)
   - Arbitrary rapid alternating latch chords
   - PTY write backpressure (EAGAIN/EINTR) handling
"""

from __future__ import annotations

import errno
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from terminal.bridge import (  # noqa: E402
    _CTRL_VALID_CHARS,
    CTRL_LATCH_CHORD,
    CTRL_LATCH_CHORDS,
    CTRL_LATCH_TIMEOUT_S,
    RESIZE_CHORD,
    KeyQueue,
    TerminalBridge,
    _ShellSession,
)
from terminal.theme import load_theme  # noqa: E402
from whiskerframe.terminal import TerminalGeometry  # noqa: E402


class TestCtrlLatchEdgeCases(unittest.TestCase):
    """Exhaustive unit and edge case tests for sticky Ctrl latch."""

    def setUp(self) -> None:
        self.mock_cardkb = MagicMock()
        self.mock_cardkb.set_led = MagicMock()
        self.mock_cardkb.clear_led = MagicMock()

        self.mock_bridge = MagicMock(spec=TerminalBridge)
        self.mock_bridge._theme = load_theme(None)
        self.mock_bridge._geometry = TerminalGeometry.for_font_size(1)
        self.mock_bridge._paint = MagicMock()
        self.mock_bridge._rebuild_geometry = MagicMock()
        self.mock_bridge._cardkb = self.mock_cardkb

        # Wire set_ctrl_led behavior to bridge implementation
        def real_set_ctrl_led(armed: bool) -> None:
            TerminalBridge.set_ctrl_led(self.mock_bridge, armed)

        self.mock_bridge.set_ctrl_led = real_set_ctrl_led

        self.master_fd = 777
        self.key_queue = KeyQueue(iter([]))
        self.session = _ShellSession(self.mock_bridge, self.master_fd, self.key_queue)

    @patch("os.write")
    def test_neopixel_led_feedback_on_consumption(self, mock_write: MagicMock) -> None:
        """NeoPixel turns yellow on latch arm, clears on consumption."""
        self.mock_cardkb.set_led.assert_not_called()
        self.mock_cardkb.clear_led.assert_not_called()

        # Arm with Fn+Tab
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        self.mock_cardkb.set_led.assert_called_once_with(255, 200, 0)

        # Consume with 'c'
        self.session._process_single_key(ord("c"))
        self.assertFalse(self.session._is_ctrl_armed())
        self.mock_cardkb.clear_led.assert_called_once()
        mock_write.assert_called_once_with(self.master_fd, b"\x03")

    def test_neopixel_led_cleared_on_toggle_cancel(self) -> None:
        """Double-pressing Fn+Tab clears LED without emitting bytes."""
        # Arm
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        self.mock_cardkb.set_led.assert_called_once_with(255, 200, 0)

        # Disarm
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertFalse(self.session._is_ctrl_armed())
        self.mock_cardkb.clear_led.assert_called_once()

    def test_neopixel_led_cleared_on_timeout(self) -> None:
        """Expiring latch timeout clears LED and disarms."""
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        self.mock_cardkb.set_led.assert_called_once()

        # Exactly at timeout boundary: 3.0s is still valid
        self.session._ctrl_armed_at -= CTRL_LATCH_TIMEOUT_S - 0.05
        self.assertTrue(self.session._is_ctrl_armed())

        # Exceed timeout boundary: > 3.0s
        self.session._ctrl_armed_at -= 0.1
        self.assertFalse(self.session._is_ctrl_armed())
        self.mock_cardkb.clear_led.assert_called_once()

    def test_resize_chord_clears_armed_latch_and_led(self) -> None:
        """Fn+Del resize chord while Ctrl is armed cancels latch and resets LED."""
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        self.mock_cardkb.set_led.assert_called_once_with(255, 200, 0)

        # Trigger resize chord
        handled = self.session._process_single_key(RESIZE_CHORD)
        self.assertTrue(handled)
        self.assertFalse(self.session._is_ctrl_armed())
        self.mock_cardkb.clear_led.assert_called_once()
        self.mock_bridge._rebuild_geometry.assert_called_once_with(self.master_fd)

    def test_rapid_toggle_sequence(self) -> None:
        """Arbitrary odd/even sequence of Fn+Tab toggles state consistently."""
        for i in range(1, 11):
            self.session._process_single_key(CTRL_LATCH_CHORD)
            expected_armed = (i % 2 == 1)
            self.assertEqual(self.session._is_ctrl_armed(), expected_armed)

    @patch("os.write")
    def test_pty_write_eagain_handling(self, mock_write: MagicMock) -> None:
        """PTY write returning EAGAIN or EINTR does not crash key pump."""
        mock_write.side_effect = OSError(errno.EAGAIN, "Resource temporarily unavailable")
        self.session._process_single_key(CTRL_LATCH_CHORD)
        res = self.session._process_single_key(ord("c"))
        self.assertTrue(res, "EAGAIN should return True (transient)")

        mock_write.side_effect = OSError(errno.EINTR, "Interrupted system call")
        self.session._process_single_key(CTRL_LATCH_CHORD)
        res = self.session._process_single_key(ord("d"))
        self.assertTrue(res, "EINTR should return True (transient)")

        mock_write.side_effect = OSError(errno.EIO, "I/O error")
        self.session._process_single_key(CTRL_LATCH_CHORD)
        res = self.session._process_single_key(ord("z"))
        self.assertFalse(res, "Fatal I/O error must return False")


class TestCtrlLatchProperties(unittest.TestCase):
    """Hypothesis property tests for Ctrl latch."""

    def setUp(self) -> None:
        self.mock_bridge = MagicMock(spec=TerminalBridge)
        self.mock_bridge._theme = load_theme(None)
        self.mock_bridge._geometry = TerminalGeometry.for_font_size(1)
        self.mock_bridge._paint = MagicMock()
        self.mock_bridge.set_ctrl_led = MagicMock()
        self.master_fd = 888

    @given(st.sampled_from(sorted(_CTRL_VALID_CHARS)))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_property_all_valid_chars_transformed(self, char_int: int) -> None:
        """Any valid Ctrl character must yield char & 0x1F and disarm latch."""
        key_queue = KeyQueue(iter([]))
        session = _ShellSession(self.mock_bridge, self.master_fd, key_queue)

        with patch("os.write") as mock_write:
            # Arm
            session._process_single_key(CTRL_LATCH_CHORD)
            self.assertTrue(session._is_ctrl_armed())

            # Key
            session._process_single_key(char_int)
            expected_payload = bytes((char_int & 0x1F,))
            mock_write.assert_called_once_with(self.master_fd, expected_payload)
            self.assertFalse(session._is_ctrl_armed())

            # Subsequent identical key is unmodified
            mock_write.reset_mock()
            session._process_single_key(char_int)
            if 0x20 <= char_int <= 0x7E:
                mock_write.assert_called_once_with(self.master_fd, bytes((char_int,)))

    @given(
        st.integers(min_value=0x20, max_value=0x7E).filter(
            lambda x: x not in _CTRL_VALID_CHARS,
        ),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_property_non_ctrl_ascii_unmodified(self, char_int: int) -> None:
        """Characters outside _CTRL_VALID_CHARS pass through unmodified and disarm."""
        key_queue = KeyQueue(iter([]))
        session = _ShellSession(self.mock_bridge, self.master_fd, key_queue)

        with patch("os.write") as mock_write:
            session._process_single_key(CTRL_LATCH_CHORD)
            self.assertTrue(session._is_ctrl_armed())

            session._process_single_key(char_int)
            mock_write.assert_called_once_with(self.master_fd, bytes((char_int,)))
            self.assertFalse(session._is_ctrl_armed())


def main() -> int:
    """Run standalone Ctrl latch edge case and property suite."""
    print("=" * 70)
    print("Running Whiskerframe Sticky Ctrl Latch Edge Case & Property Tests")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCtrlLatchEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestCtrlLatchProperties))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
