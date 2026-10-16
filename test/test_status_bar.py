"""
Unit tests for the WhiskerFrame compact status bar.

Validates:
1. Status bar state model (workspace, Wi-Fi, INA219 battery, Ctrl latch state).
2. Safe telemetry reading from /run/battery_monitor/ (status.json / uevent).
3. Responsive compact formatting across all supported geometries (53, 40, 26, 17 cols).
4. Anti-flicker architecture: grid row-isolation and zero-flicker diffing.
5. Visual feedback (yellow Ctrl latch indicator, battery health thresholds).
6. Integration with TerminalBridge _ShellSession.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from terminal.bridge import (  # noqa: E402
    BridgeConfig,
    KeyQueue,
    TerminalBridge,
    _ShellSession,
)
from terminal.grid import Cell, Grid  # noqa: E402
from terminal.status_bar import (  # noqa: E402
    StatusBar,
    read_battery_telemetry,
    read_wifi_telemetry,
)
from terminal.theme import load_theme  # noqa: E402

from whiskerframe.terminal import TerminalGeometry  # noqa: E402


class TestStatusBar(unittest.TestCase):
    """Test suite for WhiskerFrame compact status bar."""

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.status_bar = StatusBar(theme=self.theme, workspace=1, position="top")

    def test_default_initialization(self) -> None:
        """Verify default state and telemetry properties."""
        sb = StatusBar()
        self.assertEqual(sb.workspace, 1)
        self.assertEqual(sb.position, "top")
        self.assertTrue(sb.enabled)
        self.assertTrue(sb.dirty)
        self.assertFalse(sb.ctrl_latch)
        self.assertFalse(sb.wifi.connected)
        self.assertIsNone(sb.battery.percent)

    def test_state_setters_and_dirty_flag(self) -> None:
        """Verify mutators update values and trigger dirty flag."""
        sb = self.status_bar
        sb._dirty = False

        # 1. Workspace
        changed = sb.set_workspace(2)
        self.assertTrue(changed)
        self.assertEqual(sb.workspace, 2)
        self.assertTrue(sb.dirty)

        # Setting same workspace yields False
        sb._dirty = False
        self.assertFalse(sb.set_workspace(2))
        self.assertFalse(sb.dirty)

        # 2. Wi-Fi
        changed = sb.set_wifi("CyberNet", 85, True)
        self.assertTrue(changed)
        self.assertEqual(sb.wifi.ssid, "CyberNet")
        self.assertEqual(sb.wifi.signal, 85)
        self.assertTrue(sb.wifi.connected)

        # 3. Battery from INA219
        changed = sb.set_battery(92, 12.35, "Discharging")
        self.assertTrue(changed)
        self.assertEqual(sb.battery.percent, 92)
        self.assertEqual(sb.battery.voltage, 12.35)
        self.assertEqual(sb.battery.status, "Discharging")
        self.assertFalse(sb.battery.is_charging)

        # 4. Ctrl latch
        changed = sb.set_ctrl_latch(True)
        self.assertTrue(changed)
        self.assertTrue(sb.ctrl_latch)

    def test_battery_telemetry_reading_from_status_json(self) -> None:
        """Verify parsing /run/battery_monitor/status.json mirror."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "status.json"
            json_file.write_text(
                json.dumps(
                    {
                        "name": "cyberdeck_ups",
                        "voltage_v": 12.42,
                        "current_ma": -450.0,
                        "percent": 96,
                        "status": "Discharging",
                    },
                ),
                encoding="utf-8",
            )

            info = read_battery_telemetry(tmpdir)
            self.assertEqual(info.percent, 96)
            self.assertEqual(info.voltage, 12.42)
            self.assertEqual(info.status, "Discharging")
            self.assertFalse(info.is_charging)

    def test_battery_telemetry_reading_from_uevent(self) -> None:
        """Verify parsing kernel-style uevent when status.json is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uevent_file = Path(tmpdir) / "uevent"
            uevent_file.write_text(
                "POWER_SUPPLY_NAME=cyberdeck_ups\n"
                "POWER_SUPPLY_TYPE=Battery\n"
                "POWER_SUPPLY_CAPACITY=88\n"
                "POWER_SUPPLY_STATUS=Charging\n"
                "POWER_SUPPLY_VOLTAGE_NOW=12200000\n",
                encoding="utf-8",
            )

            info = read_battery_telemetry(tmpdir)
            self.assertEqual(info.percent, 88)
            self.assertEqual(info.voltage, 12.2)
            self.assertEqual(info.status, "Charging")
            self.assertTrue(info.is_charging)

    def test_battery_telemetry_safe_fallbacks(self) -> None:
        """Verify missing or corrupt files return clean safe defaults without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty dir
            info = read_battery_telemetry(tmpdir)
            self.assertIsNone(info.percent)
            self.assertIsNone(info.voltage)
            self.assertEqual(info.status, "Unknown")

            # Corrupted json
            corrupt_json = Path(tmpdir) / "status.json"
            corrupt_json.write_text("INVALID_JSON", encoding="utf-8")
            info_corrupt = read_battery_telemetry(tmpdir)
            self.assertIsNone(info_corrupt.percent)

    @patch("subprocess.run")
    def test_wifi_telemetry_reading(self, mock_run: MagicMock) -> None:
        """Verify nmcli device output parsing for active Wi-Fi."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "wlan0:wifi:connected:MyHomeAP\nlo:loopback:connected:lo\n"
        mock_run.return_value = mock_proc

        with patch("terminal.status_bar._read_active_wifi_signal", return_value=82):
            info = read_wifi_telemetry()
            self.assertTrue(info.connected)
            self.assertEqual(info.ssid, "MyHomeAP")
            self.assertEqual(info.signal, 82)

    def test_compact_formatting_across_geometries(self) -> None:
        """Verify status formatting fits strictly within each geometry's column limit."""
        sb = self.status_bar
        sb.set_workspace(1)
        sb.set_wifi("WhiskerMesh-24G", 78, True)
        sb.set_battery(94, 12.4, "Discharging")
        sb.set_ctrl_latch(True)

        geometries = [
            (53, "Font 1 (53x30)"),
            (40, "Font 5 (40x20)"),
            (26, "Font 2 (26x15)"),
            (17, "Font 3 (17x10)"),
            (12, "Ultra narrow"),
        ]

        for cols, name in geometries:
            formatted = sb.format_status(cols)
            # Must strictly equal cols width (padded to cols)
            self.assertEqual(
                len(formatted),
                cols,
                f"Failed on {name}: len={len(formatted)} != {cols}",
            )
            # Must include workspace indicator
            self.assertTrue(
                "1" in formatted or "[1]" in formatted,
                f"Workspace missing in {name}",
            )
            # Must include Ctrl latch indication when armed
            self.assertTrue(
                "[CTRL]" in formatted or "[^]" in formatted or "^" in formatted,
                f"Ctrl indicator missing in {name}",
            )

    def test_anti_flicker_grid_isolation(self) -> None:
        """
        Anti-flicker test: status bar writes only to target_row.

        1. Status bar writes only to target_row.
        2. Non-target rows remain completely identical.
        3. Diff produces runs strictly for target_row.
        """
        cols, rows = 53, 30
        grid = Grid(cols, rows, default_fg=self.theme.fg, default_bg=self.theme.bg)

        # Fill background cells with dummy content
        for r in range(rows):
            for c in range(cols):
                grid._cells[r][c] = Cell("~", self.theme.fg, self.theme.bg)

        baseline = grid.snapshot()

        # Render top status bar (row 0)
        self.status_bar.set_workspace(1)
        self.status_bar.set_battery(95, 12.4)
        self.status_bar.render_to_grid(grid)

        # Check that rows 1 to 29 are untouched
        untouched = all(
            grid.cell_at(r, c).char == "~" for r in range(1, rows) for c in range(cols)
        )
        self.assertTrue(untouched, "Non-status rows were modified by status bar!")

        # Check diff against baseline: all runs must be row 0
        runs = grid.diff(baseline)
        self.assertTrue(len(runs) > 0)
        self.assertTrue(
            all(run.row == 0 for run in runs),
            "Run generated on non-target row",
        )

    def test_anti_flicker_zero_transmission_when_unchanged(self) -> None:
        """
        Anti-flicker test: zero transmission when telemetry unchanged.

        When status bar telemetry is unchanged, re-rendering produces 0 diff runs.
        """
        cols, rows = 53, 30
        grid = Grid(cols, rows, default_fg=self.theme.fg, default_bg=self.theme.bg)
        self.status_bar.render_to_grid(grid)

        prev_snapshot = grid.snapshot()

        # Re-render without state changes
        self.status_bar.render_to_grid(grid)
        diff_runs = grid.diff(prev_snapshot)

        # 0 changed cells = 0 runs sent = 0 serial bytes = 0 redraw flicker!
        self.assertEqual(len(diff_runs), 0)

    def test_anti_flicker_minimal_run_on_delta(self) -> None:
        """
        Anti-flicker test: minimal run emitted on delta.

        When only one field updates (e.g. battery 94% -> 95%), only the status
        row emits a small update, without touching any other part of the screen.
        """
        cols, rows = 53, 30
        grid = Grid(cols, rows, default_fg=self.theme.fg, default_bg=self.theme.bg)
        self.status_bar.set_battery(94, 12.4)
        self.status_bar.render_to_grid(grid)

        prev = grid.snapshot()

        # Telemetry tick: battery increments
        self.status_bar.set_battery(95, 12.4)
        self.status_bar.render_to_grid(grid)

        runs = grid.diff(prev)
        self.assertTrue(len(runs) >= 1)
        # All runs strictly on row 0
        for r in runs:
            self.assertEqual(r.row, 0)

    def test_ctrl_latch_visual_feedback(self) -> None:
        """Verify yellow color feedback when Ctrl latch is armed."""
        grid = Grid(53, 30, self.theme.fg, self.theme.bg)

        # Disarmed
        self.status_bar.set_ctrl_latch(False)
        self.status_bar.render_to_grid(grid)
        disarmed_text = self.status_bar._last_formatted
        self.assertNotIn("[CTRL]", disarmed_text)

        # Armed
        self.status_bar.set_ctrl_latch(True)
        self.status_bar.render_to_grid(grid)
        armed_text = self.status_bar._last_formatted
        self.assertIn("[CTRL]", armed_text)

        # Locate [CTRL] in row 0 cells and check yellow foreground
        ctrl_col = armed_text.index("[CTRL]")
        cell = grid.cell_at(0, ctrl_col)
        self.assertEqual(cell.fg, self.theme.ansi[11])  # bright yellow

    def test_position_bottom(self) -> None:
        """Verify status bar renders at bottom row when position='bottom'."""
        cols, rows = 40, 20
        grid = Grid(cols, rows, self.theme.fg, self.theme.bg)
        sb = StatusBar(theme=self.theme, position="bottom")
        self.assertEqual(sb.target_row(grid), 19)

        sb.render_to_grid(grid)
        # Verify row 19 has content and row 0 is blank
        self.assertNotEqual(grid.cell_at(19, 0).char, " ")
        self.assertEqual(grid.cell_at(0, 0).char, " ")

    def test_shell_session_integration(self) -> None:
        """Verify _ShellSession renders status bar onto display_grid during _paint_session."""
        mock_bridge = MagicMock(spec=TerminalBridge)
        mock_bridge._theme = self.theme
        mock_bridge._geometry = TerminalGeometry.for_font_size(2)
        mock_bridge._paint = MagicMock()
        mock_bridge._config = BridgeConfig(
            theme=self.theme,
            status_bar_enabled=True,
            status_bar_position="top",
        )

        key_queue = KeyQueue(iter([]))
        session = _ShellSession(mock_bridge, 888, key_queue)

        # Status bar should be initialized
        self.assertIsNotNone(session._status_bar)

        # Call paint session
        session._paint_session()

        # Check the painted grid passed to bridge._paint
        self.assertTrue(mock_bridge._paint.called)
        painted_grid = mock_bridge._paint.call_args[0][0]

        # Verify row 0 contains status bar content
        row_0_chars = "".join(
            painted_grid.cell_at(0, c).char for c in range(painted_grid.cols)
        )
        self.assertTrue("[" in row_0_chars and "]" in row_0_chars)


if __name__ == "__main__":
    unittest.main()
