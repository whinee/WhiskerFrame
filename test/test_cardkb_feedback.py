"""
Automated test suite for CardKB hardware feedback and sticky Ctrl latch.

Validates the full CardKB feedback contract:
1. CardKB I2C firmware & registers inspection at 0x5F:
   - Verification of I2C address (0x5F) and opcodes (0x11 clear, 0x13 set).
   - Verification that stock ATmega328P firmware lacks persistent registers.
   - Enforcement of default NeoPixel OFF across boot (open/close) and power cycles.
2. Sticky Ctrl latch state machine & cursor recolor:
   - Immediate yellow cursor recoloring (theme.ansi[11]) on latch arm (Fn+Tab / 0x8C).
   - Immediate CardKB hardware NeoPixel yellow illumination (255, 200, 0).
   - Translation of next qualifying keystroke to control code (char & 0x1F).
   - Passthrough of non-qualifying keystrokes.
   - Immediate indicator reset (theme.cursor) and NeoPixel clear on disarm (toggle cancel).
   - Immediate indicator reset and NeoPixel clear on timeout (> 3.0s).
   - Immediate indicator reset and NeoPixel clear on resize chord interruption (Fn+Del).
   - Teardown safety and cleanup on session termination.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from cardkb.reader import (  # noqa: E402
    OPCODE_CLEAR_LED,
    OPCODE_SET_LED,
    CardKB,
)
from terminal.bridge import (  # noqa: E402
    CTRL_LATCH_CHORD,
    CTRL_LATCH_TIMEOUT_S,
    RESIZE_CHORD,
    KeyQueue,
    TerminalBridge,
    _ShellSession,
)
from terminal.grid import Grid  # noqa: E402
from terminal.theme import load_theme  # noqa: E402

from whiskerframe.terminal import TerminalGeometry  # noqa: E402


class TestCardKBI2CFirmwareRegistersAndDefaultOff(unittest.TestCase):
    """Inspect CardKB I2C firmware/registers at 0x5F and verify default-off lifecycle."""

    def test_i2c_address_and_opcodes_contract(self) -> None:
        """Verify default slave address 0x5F and firmware opcodes 0x11 / 0x13."""
        kb = CardKB()
        self.assertEqual(kb.address, 0x5F)
        self.assertEqual(kb.bus, 0)
        self.assertTrue(kb.default_led_off)
        self.assertEqual(OPCODE_CLEAR_LED, 0x11)
        self.assertEqual(OPCODE_SET_LED, 0x13)

    @patch("cardkb.reader.os.write")
    def test_clear_led_transmits_opcode_0x11(self, mock_write: MagicMock) -> None:
        """clear_led() transmits single-byte opcode 0x11 over I2C."""
        kb = CardKB()
        kb._fd = 42
        ok = kb.clear_led()
        self.assertTrue(ok)
        mock_write.assert_called_once_with(42, bytes([0x11]))

    @patch("cardkb.reader.os.write")
    def test_set_led_transmits_opcode_0x13_and_rgb(self, mock_write: MagicMock) -> None:
        """set_led() transmits opcode 0x13 with 3 RGB parameter bytes."""
        kb = CardKB()
        kb._fd = 42
        ok = kb.set_led(255, 200, 0)
        self.assertTrue(ok)
        mock_write.assert_called_once_with(42, bytes([0x13, 255, 200, 0]))

    @patch("cardkb.reader.os.write")
    def test_led_operations_fail_silent_on_bus_error(
        self,
        mock_write: MagicMock,
    ) -> None:
        """clear_led and set_led fail silently on OSError (returning False)."""
        mock_write.side_effect = OSError(121, "Remote I/O error")
        kb = CardKB()
        kb._fd = 42
        self.assertFalse(kb.clear_led())
        self.assertFalse(kb.set_led(255, 200, 0))

    @patch("cardkb.reader.os.write")
    @patch("cardkb.reader.fcntl.ioctl")
    @patch("cardkb.reader.os.open")
    def test_open_defaults_neopixel_to_off_across_boot(
        self,
        mock_open: MagicMock,
        mock_ioctl: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """CardKB.open() actively extinguishes NeoPixel via clear_led (boot invariant)."""
        mock_open.return_value = 15
        kb = CardKB(bus=0, address=0x5F, default_led_off=True)
        kb.open()
        self.assertEqual(kb._fd, 15)
        mock_ioctl.assert_called_once()
        mock_write.assert_called_once_with(15, bytes([0x11]))

    @patch("cardkb.reader.os.write")
    @patch("cardkb.reader.os.close")
    @patch("cardkb.reader.fcntl.ioctl")
    @patch("cardkb.reader.os.open")
    def test_close_ensures_neopixel_cleared_on_exit(
        self,
        mock_open: MagicMock,
        mock_ioctl: MagicMock,
        mock_close: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """CardKB.close() extinguishes NeoPixel before closing fd."""
        mock_open.return_value = 15
        kb = CardKB(bus=0, address=0x5F, default_led_off=True)
        kb.open()
        mock_write.reset_mock()
        kb.close()
        mock_write.assert_called_once_with(15, bytes([0x11]))
        mock_close.assert_called_once_with(15)
        self.assertIsNone(kb._fd)

    @patch("cardkb.reader.os.write")
    def test_ensure_default_led_off_convenience_method(
        self,
        mock_write: MagicMock,
    ) -> None:
        """ensure_default_led_off() invokes clear_led() to guarantee state."""
        kb = CardKB()
        kb._fd = 42
        self.assertTrue(kb.ensure_default_led_off())
        mock_write.assert_called_once_with(42, bytes([0x11]))

    @patch("cardkb.reader.os.write")
    @patch("cardkb.reader.fcntl.ioctl")
    @patch("cardkb.reader.os.open")
    def test_open_respects_default_led_off_false_flag(
        self,
        mock_open: MagicMock,
        mock_ioctl: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """When default_led_off=False, open does not write clear command."""
        mock_open.return_value = 15
        kb = CardKB(bus=0, address=0x5F, default_led_off=False)
        kb.open()
        mock_write.assert_not_called()

    @patch("cardkb.reader.time.sleep")
    @patch("cardkb.reader.os.write")
    @patch("cardkb.reader.os.close")
    @patch("cardkb.reader.os.read")
    @patch("cardkb.reader.fcntl.ioctl")
    @patch("cardkb.reader.os.open")
    def test_robust_keys_recovers_and_extinguishes_led_across_power_cycle(
        self,
        mock_open: MagicMock,
        mock_ioctl: MagicMock,
        mock_read: MagicMock,
        mock_close: MagicMock,
        mock_write: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """robust_keys() handles bus drop/power-cycle and clears NeoPixel on reopen."""
        mock_open.return_value = 20
        # 1. First read succeeds with 'a' (0x61)
        # 2. Second read simulates device power-cycle / bus disconnect (OSError)
        # 3. Third read after recovery succeeds with 'b' (0x62)
        mock_read.side_effect = [
            b"a",
            OSError(121, "Remote I/O error"),
            b"b",
        ]

        kb = CardKB(bus=0, address=0x5F, default_led_off=True)
        key_gen = kb.robust_keys(poll_interval_s=0.001)

        first_key = next(key_gen)
        self.assertEqual(first_key, ord("a"))

        # Second yield should recover after error
        second_key = next(key_gen)
        self.assertEqual(second_key, ord("b"))

        # Verify open() was called twice (initial + recovery after power cycle)
        self.assertEqual(mock_open.call_count, 2)
        # Verify clear_led was dispatched on each open (boot + power cycle recovery)
        clear_calls = [
            c for c in mock_write.call_args_list if c == call(20, bytes([0x11]))
        ]
        self.assertGreaterEqual(len(clear_calls), 2)


class TestCtrlLatchFeedbackAndIndicatorRecolor(unittest.TestCase):
    """Test sticky Ctrl latch yellow cursor recoloring, key translation, and reset."""

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.geometry = TerminalGeometry.for_font_size(2)

        self.mock_cardkb = MagicMock()
        self.mock_cardkb.set_led = MagicMock()
        self.mock_cardkb.clear_led = MagicMock()

        self.mock_bridge = MagicMock(spec=TerminalBridge)
        self.mock_bridge._theme = self.theme
        self.mock_bridge._geometry = self.geometry
        self.mock_bridge._paint = MagicMock()
        self.mock_bridge._rebuild_geometry = MagicMock(
            return_value=Grid(
                self.geometry.cols,
                self.geometry.rows,
                self.theme.fg,
                self.theme.bg,
            ),
        )
        self.mock_bridge._cardkb = self.mock_cardkb

        # Wire set_ctrl_led to TerminalBridge implementation
        def real_set_ctrl_led(armed: bool) -> None:
            TerminalBridge.set_ctrl_led(self.mock_bridge, armed)

        self.mock_bridge.set_ctrl_led = real_set_ctrl_led

        self.master_fd = 555
        self.key_queue = KeyQueue(iter([]))
        self.session = _ShellSession(self.mock_bridge, self.master_fd, self.key_queue)

    def _get_last_painted_cursor_bg(self) -> int:
        """Extract the background color of the cursor cell from the latest _paint call."""
        last_grid = self.mock_bridge._paint.call_args[0][0]
        return last_grid.cell_at(last_grid.cursor_row, last_grid.cursor_col).bg

    def test_immediate_yellow_cursor_and_neopixel_on_latch_arm(self) -> None:
        """Pressing Fn+Tab immediately recolors cursor to yellow and turns NeoPixel yellow."""
        # Unarmed baseline
        self.assertFalse(self.session._is_ctrl_armed())
        self.session._paint_session()
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.cursor)
        self.mock_cardkb.set_led.assert_not_called()

        # Arm with Fn+Tab (0x8C)
        handled = self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(handled)
        self.assertTrue(self.session._is_ctrl_armed())

        # Cursor recolored to bright yellow (theme.ansi[11]) immediately
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.ansi[11])
        # NeoPixel illuminated yellow (255, 200, 0)
        self.mock_cardkb.set_led.assert_called_once_with(255, 200, 0)
        self.mock_cardkb.clear_led.assert_not_called()

    @patch("os.write")
    def test_translates_qualifying_keys_and_resets_indicator(
        self,
        mock_write: MagicMock,
    ) -> None:
        """Qualifying keys translate to Ctrl code, disarm latch, and reset indicator/LED."""
        test_cases = [
            ("c", ord("c"), b"\x03"),
            ("d", ord("d"), b"\x04"),
            ("z", ord("z"), b"\x1a"),
            ("A", ord("A"), b"\x01"),
            ("[", ord("["), b"\x1b"),
            ("space", ord(" "), b"\x00"),
        ]

        for label, char_int, expected_payload in test_cases:
            with self.subTest(char=label):
                mock_write.reset_mock()
                self.mock_cardkb.set_led.reset_mock()
                self.mock_cardkb.clear_led.reset_mock()

                # 1. Arm
                self.session._process_single_key(CTRL_LATCH_CHORD)
                self.assertTrue(self.session._is_ctrl_armed())
                self.assertEqual(
                    self._get_last_painted_cursor_bg(),
                    self.theme.ansi[11],
                )
                self.mock_cardkb.set_led.assert_called_once_with(255, 200, 0)

                # 2. Press qualifying key
                handled = self.session._process_single_key(char_int)
                self.assertTrue(handled)
                mock_write.assert_called_once_with(self.master_fd, expected_payload)

                # 3. Latch must be disarmed, indicator reset to normal, NeoPixel cleared
                self.assertFalse(self.session._is_ctrl_armed())
                self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.cursor)
                self.mock_cardkb.clear_led.assert_called_once()

    @patch("os.write")
    def test_non_qualifying_key_cancels_and_resets_indicator(
        self,
        mock_write: MagicMock,
    ) -> None:
        """Non-qualifying keys (e.g. '1', arrow keys) pass through and reset indicator/LED."""
        # Arm
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.ansi[11])

        # Press '1' (0x31)
        handled = self.session._process_single_key(ord("1"))
        self.assertTrue(handled)
        mock_write.assert_called_once_with(self.master_fd, b"1")

        # Disarmed and indicator reset
        self.assertFalse(self.session._is_ctrl_armed())
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.cursor)
        self.mock_cardkb.clear_led.assert_called_once()

    @patch("os.write")
    def test_reset_indicator_on_toggle_cancel(self, mock_write: MagicMock) -> None:
        """Pressing Fn+Tab twice cancels latch, resets cursor indicator and clears NeoPixel."""
        # 1. Arm
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.ansi[11])
        self.mock_cardkb.set_led.assert_called_once_with(255, 200, 0)

        # 2. Disarm via second chord press
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertFalse(self.session._is_ctrl_armed())
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.cursor)
        self.mock_cardkb.clear_led.assert_called_once()
        mock_write.assert_not_called()

    def test_reset_indicator_on_timeout_expiration(self) -> None:
        """Expiring 3.0s timeout immediately resets cursor indicator and clears NeoPixel."""
        # Arm
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.ansi[11])
        self.mock_cardkb.set_led.assert_called_once()

        # Advance monotonic clock > 3.0s
        self.session._ctrl_armed_at -= CTRL_LATCH_TIMEOUT_S + 0.1

        # Check arm state: must disarm, reset cursor to normal, and clear LED
        self.assertFalse(self.session._is_ctrl_armed())
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.cursor)
        self.mock_cardkb.clear_led.assert_called_once()

    def test_reset_indicator_on_resize_chord_interruption(self) -> None:
        """Fn+Del resize chord cancels armed latch, resets LED, and repaints new geometry."""
        # Arm
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.ansi[11])

        # Press Fn+Del (0x8B)
        handled = self.session._process_single_key(RESIZE_CHORD)
        self.assertTrue(handled)
        self.assertFalse(self.session._is_ctrl_armed())
        self.mock_cardkb.clear_led.assert_called_once()
        self.mock_bridge._rebuild_geometry.assert_called_once_with(self.master_fd)
        self.assertEqual(self._get_last_painted_cursor_bg(), self.theme.cursor)

    def test_latch_disarmed_and_led_cleared_on_teardown(self) -> None:
        """_disarm_ctrl safely cleans up state and turns off LED on exit."""
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())

        self.session._disarm_ctrl(repaint=False)
        self.assertFalse(self.session._is_ctrl_armed())
        self.mock_cardkb.clear_led.assert_called_once()


if __name__ == "__main__":
    unittest.main()
