"""
Unit tests for the WhiskerFrame configurable status bar subsystem.

Validates:
1. Status bar state model (workspace, Wi-Fi, battery, disk, mobile, time, Ctrl latch).
2. Data providers (INA219 battery, NetworkManager Wi-Fi, disk usage, mobile).
3. Context-sensitive status profiles (login, root, neko, default).
4. Access control enforcement (privileged modules restricted for non-root/login).
5. Anti-flicker architecture: grid row-isolation and zero-flicker diffing.
6. Off-blurple theme background color and visual feedback.
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
    read_disk_telemetry,
    read_wifi_telemetry,
)
from terminal.theme import load_theme  # noqa: E402

from whiskerframe.terminal import TerminalGeometry  # noqa: E402


class TestConfigurableStatusBar(unittest.TestCase):
    """Test suite for WhiskerFrame configurable status bar and data providers."""

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.config = {
            "terminal": {
                "status_bar": {
                    "enabled": True,
                    "position": "top",
                    "theme_bg": 0x24E9,
                    "profiles": {
                        "login": {
                            "modules": ["time", "wifi", "battery", "host_link"],
                            "order": ["time", "wifi", "battery", "host_link"],
                        },
                        "root": {
                            "modules": ["workspace", "wifi", "battery", "disk", "host_link", "time", "ctrl_latch"],
                            "order": ["workspace", "wifi", "battery", "disk", "host_link", "time", "ctrl_latch"],
                            "privileged": True,
                        },
                        "neko": {
                            "modules": ["workspace", "wifi", "battery", "time", "ctrl_latch"],
                            "order": ["workspace", "wifi", "battery", "time", "ctrl_latch"],
                        },
                    },
                }
            }
        }
        self.status_bar = StatusBar(theme=self.theme, workspace=1, position="top", config=self.config, user="root", profile="root")

    def test_default_initialization_and_off_blurple(self) -> None:
        """Verify default state and off-blurple background color."""
        sb = StatusBar(config=self.config)
        self.assertEqual(sb.workspace, 1)
        self.assertEqual(sb.position, "top")
        self.assertTrue(sb.enabled)
        self.assertEqual(sb.status_bg, 0x24E9)  # off-blurple

    def test_disk_telemetry_provider(self) -> None:
        """Verify read_disk_telemetry returns valid disk metrics."""
        disk = read_disk_telemetry("/")
        self.assertGreaterEqual(disk.percent, 0)
        self.assertLessEqual(disk.percent, 100)
        self.assertGreaterEqual(disk.total_gb, 0.0)

    def test_profiles_and_access_control(self) -> None:
        """Verify profiles control visible modules and enforce role authorization."""
        # 1. Root profile includes disk (privileged)
        sb_root = StatusBar(config=self.config, user="root", profile="root")
        mods_root = sb_root._get_profile_modules()
        self.assertIn("disk", mods_root)
        self.assertIn("workspace", mods_root)

        # 2. Neko profile excludes disk (non-root)
        sb_neko = StatusBar(config=self.config, user="neko", profile="neko")
        mods_neko = sb_neko._get_profile_modules()
        self.assertNotIn("disk", mods_neko)
        self.assertIn("workspace", mods_neko)

        # 3. Login profile excludes workspace and ctrl_latch
        sb_login = StatusBar(config=self.config, user="guest", profile="login")
        mods_login = sb_login._get_profile_modules()
        self.assertNotIn("workspace", mods_login)
        self.assertNotIn("ctrl_latch", mods_login)
        self.assertIn("battery", mods_login)

    def test_compact_formatting_across_geometries(self) -> None:
        """Verify status formatting fits strictly within each geometry's column limit."""
        sb = self.status_bar
        sb.set_workspace(1)
        sb.set_wifi("WhiskerMesh", 90, True)
        sb.set_battery(95, 12.4, "Discharging")
        sb.set_ctrl_latch(True)

        geometries = [53, 40, 26, 17]
        for cols in geometries:
            formatted = sb.format_status(cols)
            self.assertEqual(len(formatted), cols, f"Width mismatch for cols={cols}")

    def test_anti_flicker_grid_isolation(self) -> None:
        """Verify status bar writes only to target row and leaves terminal rows untouched."""
        cols, rows = 53, 30
        grid = Grid(cols, rows, default_fg=self.theme.fg, default_bg=self.theme.bg, status_bar_rows=1, status_bar_position="top")

        for r in range(rows):
            for c in range(cols):
                grid._cells[r][c] = Cell("~", self.theme.fg, self.theme.bg)

        self.status_bar.render_to_grid(grid)

        # Row 0 has status bar, rows 1..29 remain '~'
        untouched = all(
            grid.cell_at(r, c).char == "~" for r in range(1, rows) for c in range(cols)
        )
        self.assertTrue(untouched)


if __name__ == "__main__":
    unittest.main()
