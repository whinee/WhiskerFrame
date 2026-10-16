"""
Compact status bar for the WhiskerFrame cyberdeck terminal.

Renders system telemetry into a dedicated terminal row without causing full-screen
redraw flicker. Displays:
1. Active workspace identifier (e.g. [1], [ws1])
2. Wi-Fi status (SSID, signal strength %, connection state)
3. Battery status from INA219 (voltage, %, charge/discharge status)
4. CardKB sticky Ctrl modifier latch state (Fn+Tab indicator, highlighted in yellow)

Anti-Flicker Architecture:
The status bar writes strictly to its designated row in the terminal Grid (by default
row 0, or the bottom row). When Grid.diff(prev_grid) computes the screen update:
- Unchanged terminal rows yield 0 draw runs.
- If status telemetry has not changed, 0 draw runs are emitted for the status row.
- When telemetry changes, only the modified cells in the status bar row are coalesced
  into a single compact DRAW_CELLS command (18-69 bytes over serial).
- The full panel is NEVER cleared (_clear_panel is not called), completely eliminating
  visual redraw flicker.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .grid import Cell, Grid
from .theme import Theme, load_theme

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "BatteryInfo",
    "StatusBar",
    "WifiInfo",
    "read_battery_telemetry",
    "read_wifi_telemetry",
]

_DEFAULT_BATTERY_DIR = Path("/run/battery_monitor")


@dataclass(frozen=True)
class BatteryInfo:
    """Resolved battery telemetry from INA219 monitor."""

    percent: int | None
    voltage: float | None
    status: str  # "Charging", "Discharging", "Full", "Not charging", or "Unknown"

    @property
    def is_charging(self) -> bool:
        """Report whether the battery is actively charging."""
        return self.status in ("Charging", "Full")


@dataclass(frozen=True)
class WifiInfo:
    """Resolved Wi-Fi telemetry from NetworkManager or system state."""

    ssid: str | None
    signal: int | None
    connected: bool


def read_battery_telemetry(run_dir: Path | str = _DEFAULT_BATTERY_DIR) -> BatteryInfo:
    """
    Read battery telemetry from /run/battery_monitor/status.json or uevent mirror.

    Safe and total: returns BatteryInfo(None, None, "Unknown") on any missing file
    or parse error. Never raises an exception.

    Args:
    - run_dir (`Path | str`, optional): Path to battery monitor run directory.

    Returns:
    `BatteryInfo`: Resolved battery percentage, bus voltage, and charge state.
    """
    path = Path(run_dir)
    json_path = path / "status.json"
    if json_path.is_file():
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            pct = data.get("percent")
            volt = data.get("voltage_v")
            st = data.get("status", "Unknown")
            return BatteryInfo(
                percent=int(pct) if pct is not None else None,
                voltage=float(volt) if volt is not None else None,
                status=str(st),
            )
        except (OSError, ValueError, TypeError):
            pass

    # Fallback: check kernel-style uevent mirror
    uevent_path = path / "uevent"
    if uevent_path.is_file():
        try:
            pct_val: int | None = None
            volt_val: float | None = None
            st_val = "Unknown"
            with open(uevent_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("POWER_SUPPLY_CAPACITY="):
                        pct_val = int(line.split("=", 1)[1])
                    elif line.startswith("POWER_SUPPLY_VOLTAGE_NOW="):
                        # microvolts to volts
                        volt_val = round(int(line.split("=", 1)[1]) / 1_000_000.0, 2)
                    elif line.startswith("POWER_SUPPLY_STATUS="):
                        st_val = line.split("=", 1)[1]
            return BatteryInfo(percent=pct_val, voltage=volt_val, status=st_val)
        except (OSError, ValueError, TypeError):
            pass

    return BatteryInfo(percent=None, voltage=None, status="Unknown")


def read_wifi_telemetry() -> WifiInfo:
    """
    Read active Wi-Fi telemetry using nmcli or cache file with safe fallback.

    Returns:
    `WifiInfo`: Resolved SSID, signal strength %, and connection flag.
    """
    # 1. Try quick nmcli device status
    try:
        res = subprocess.run(  # noqa: S603, S607
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.strip().split(":")
                if len(parts) >= 4 and parts[1] == "wifi" and parts[2] == "connected":
                    active_conn = parts[3]
                    # Query signal strength for active connection
                    sig = _read_active_wifi_signal()
                    return WifiInfo(ssid=active_conn, signal=sig, connected=True)
    except (OSError, subprocess.SubprocessError):
        pass

    # 2. Check /tmp/wifi-scan.json cache if present
    cache_path = Path("/tmp/wifi-scan.json")  # noqa: S108
    if cache_path.is_file():
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache_data = json.load(f)
            networks = cache_data.get("networks", [])
            if networks:
                top = networks[0]
                return WifiInfo(
                    ssid=str(top.get("ssid", "Wi-Fi")),
                    signal=int(top.get("signal", 0)),
                    connected=True,
                )
        except (OSError, ValueError):
            pass

    return WifiInfo(ssid=None, signal=None, connected=False)


def _read_active_wifi_signal() -> int | None:
    """Helper to query signal strength % of currently active Wi-Fi AP."""
    try:
        res = subprocess.run(  # noqa: S603, S607
            ["nmcli", "-t", "-f", "IN-USE,SIGNAL", "dev", "wifi"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.strip().split(":")
                if len(parts) >= 2 and parts[0] == "*":
                    digits = re.sub(r"\D", "", parts[1])
                    return int(digits) if digits else None
    except (OSError, subprocess.SubprocessError):
        pass
    return None


class StatusBar:
    """
    Compact status bar maintaining system telemetry and rendering to a Grid.

    Attributes:
    - workspace (`str | int`): Current workspace identifier.
    - wifi (`WifiInfo`): Current Wi-Fi telemetry.
    - battery (`BatteryInfo`): Current battery telemetry from INA219.
    - ctrl_latch (`bool`): Whether CardKB sticky Ctrl modifier latch is armed.
    - position (`str`): "top" (row 0) or "bottom" (row `rows - 1`).
    - row (`int | None`): Explicit row index override.
    - theme (`Theme`): The active color theme.
    """

    def __init__(
        self,
        theme: Theme | None = None,
        workspace: str | int = 1,
        position: str = "top",
        row: int | None = None,
        enabled: bool = True,
    ) -> None:
        """
        Initialize the status bar with optional custom configuration.

        Args:
        - theme (`Theme | None`, optional): RGB565 theme. Defaults to load_theme().
        - workspace (`str | int`, optional): Starting workspace. Defaults to 1.
        - position (`str`, optional): "top" or "bottom". Defaults to "top".
        - row (`int | None`, optional): Explicit target row index.
        - enabled (`bool`, optional): Master enable toggle. Defaults to True.
        """
        self.theme: Theme = theme if theme is not None else load_theme(None)
        self.workspace: str | int = workspace
        self.position: str = position.lower()
        self.row: int | None = row
        self.enabled: bool = enabled

        self.wifi: WifiInfo = WifiInfo(ssid=None, signal=None, connected=False)
        self.battery: BatteryInfo = BatteryInfo(percent=None, voltage=None, status="Unknown")
        self.ctrl_latch: bool = False

        self._dirty: bool = True
        self._last_formatted: str = ""

    @property
    def dirty(self) -> bool:
        """Report whether telemetry has mutated since last render."""
        return self._dirty

    def set_workspace(self, ws: str | int) -> bool:
        """Update active workspace. Returns True if value changed."""
        if self.workspace != ws:
            self.workspace = ws
            self._dirty = True
            return True
        return False

    def set_wifi(
        self,
        ssid: str | None,
        signal: int | None = None,
        connected: bool = True,
    ) -> bool:
        """Update Wi-Fi telemetry manually. Returns True if changed."""
        new_info = WifiInfo(ssid=ssid, signal=signal, connected=connected)
        if self.wifi != new_info:
            self.wifi = new_info
            self._dirty = True
            return True
        return False

    def set_battery(
        self,
        percent: int | None,
        voltage: float | None = None,
        status: str = "Discharging",
    ) -> bool:
        """Update battery telemetry manually. Returns True if changed."""
        new_info = BatteryInfo(percent=percent, voltage=voltage, status=status)
        if self.battery != new_info:
            self.battery = new_info
            self._dirty = True
            return True
        return False

    def set_ctrl_latch(self, armed: bool) -> bool:
        """Update sticky Ctrl latch modifier state. Returns True if changed."""
        if self.ctrl_latch != armed:
            self.ctrl_latch = armed
            self._dirty = True
            return True
        return False

    def refresh_telemetry(
        self,
        battery_dir: Path | str = _DEFAULT_BATTERY_DIR,
    ) -> bool:
        """
        Poll battery and Wi-Fi telemetry from system mirrors.

        Returns:
        `bool`: True if any field changed.
        """
        changed = False
        new_bat = read_battery_telemetry(battery_dir)
        if self.battery != new_bat:
            self.battery = new_bat
            changed = True

        new_wifi = read_wifi_telemetry()
        if self.wifi != new_wifi:
            self.wifi = new_wifi
            changed = True

        if changed:
            self._dirty = True
        return changed

    def target_row(self, grid: Grid) -> int:
        """Resolve the 0-indexed row on the target grid for this status bar."""
        if self.row is not None:
            return max(0, min(self.row, grid.rows - 1))
        if self.position == "bottom":
            return max(0, grid.rows - 1)
        return 0  # top

    def format_status(self, cols: int) -> str:
        """
        Format a single-line compact status string strictly constrained to cols width.

        Adapts dynamically to the active terminal geometry:
        - cols >= 48 (53x30 geometry): Full details with voltages and full labels.
        - cols >= 35 (40x20 geometry): Compact labels with voltage and signal.
        - cols >= 22 (26x15 geometry): Ultra-compact badges.
        - cols < 22  (17x10 geometry): Minimalist short codes.

        Args:
        - cols (`int`): Target column width.

        Returns:
        `str`: Formatted status string padded with trailing spaces to exactly cols.
        """
        ws_str = f"[{self.workspace}]"

        # Format Wi-Fi badge
        if self.wifi.connected and self.wifi.ssid:
            raw_ssid = self.wifi.ssid
            sig = f"{self.wifi.signal}%" if self.wifi.signal is not None else ""
            if cols >= 48:
                ssid_disp = raw_ssid[:12] + "~" if len(raw_ssid) > 13 else raw_ssid
                wifi_badge = f"WiFi:{ssid_disp} {sig}".strip()
            elif cols >= 35:
                ssid_disp = raw_ssid[:8] + "~" if len(raw_ssid) > 9 else raw_ssid
                wifi_badge = f"{ssid_disp} {sig}".strip()
            elif cols >= 22:
                ssid_disp = raw_ssid[:6] + "~" if len(raw_ssid) > 7 else raw_ssid
                wifi_badge = ssid_disp
            else:
                wifi_badge = "WiFi"
        else:
            wifi_badge = "WiFi:--" if cols >= 35 else "--"

        # Format Battery badge
        if self.battery.percent is not None:
            pct_str = f"{self.battery.percent}%"
            chg_char = "+" if self.battery.is_charging else ""
            if cols >= 48 and self.battery.voltage is not None:
                bat_badge = f"Bat:{self.battery.voltage:.1f}V {pct_str}{chg_char}"
            elif cols >= 35 and self.battery.voltage is not None:
                bat_badge = f"{self.battery.voltage:.1f}V {pct_str}{chg_char}"
            else:
                bat_badge = f"{pct_str}{chg_char}"
        else:
            bat_badge = "Bat:--" if cols >= 35 else "BAT"

        # Format Ctrl latch badge
        ctrl_badge = "[CTRL]" if self.ctrl_latch else ""
        if cols < 35 and self.ctrl_latch:
            ctrl_badge = "[^]"

        # Assemble responsive layout
        if cols >= 48:
            # 53 columns: [1]  WiFi:SSID 77%  Bat:12.4V 95%  [CTRL]
            core = f"{ws_str}  {wifi_badge}  {bat_badge}"
            if ctrl_badge:
                pad_needed = cols - len(core) - len(ctrl_badge) - 1
                if pad_needed > 0:
                    raw = f"{core}{' ' * pad_needed}{ctrl_badge}"
                else:
                    raw = f"{core} {ctrl_badge}"
            else:
                raw = core
        elif cols >= 35:
            # 40 columns: [1] SSID 77% | 12.4V 95% [^]
            core = f"{ws_str} {wifi_badge} | {bat_badge}"
            if ctrl_badge:
                pad_needed = cols - len(core) - len(ctrl_badge) - 1
                if pad_needed > 0:
                    raw = f"{core}{' ' * pad_needed}{ctrl_badge}"
                else:
                    raw = f"{core} {ctrl_badge}"
            else:
                raw = core
        elif cols >= 22:
            # 26 columns: [1] SSID | 95% [^]
            core = f"{ws_str} {wifi_badge} | {bat_badge}"
            if ctrl_badge:
                pad_needed = cols - len(core) - len(ctrl_badge) - 1
                if pad_needed > 0:
                    raw = f"{core}{' ' * pad_needed}{ctrl_badge}"
                else:
                    raw = f"{core} {ctrl_badge}"
            else:
                raw = core
        else:
            # 17 columns: 1|WiFi|95%|^
            w_short = str(self.workspace)[:1]
            ctrl_short = "^" if self.ctrl_latch else ""
            raw = f"{w_short}|{wifi_badge[:4]}|{bat_badge[:4]}|{ctrl_short}".rstrip("|")

        # Constrain to exactly cols
        truncated = raw[:cols]
        padded = truncated.ljust(cols, " ")
        self._last_formatted = padded
        return padded

    def render_to_grid(self, grid: Grid, row: int | None = None) -> bool:
        """
        Render the status bar into the designated row of the target grid.

        Anti-Flicker Guarantee:
        Mutates ONLY grid._cells[target_row] and touches no other cells. When
        grid.diff(prev_grid) is invoked, only this single row produces CellRun
        commands. If the status bar content is unchanged, 0 runs are emitted.

        Args:
        - grid (`Grid`): Target terminal grid.
        - row (`int | None`, optional): Row override. Defaults to configured row.

        Returns:
        `bool`: True if rendered, False if disabled.
        """
        if not self.enabled:
            return False

        target_row = self.target_row(grid) if row is None else max(0, min(row, grid.rows - 1))
        text = self.format_status(grid.cols)

        # Style colors:
        # Background: dark slate / dark accent (theme.ansi[8] or high-contrast theme.bg)
        status_bg = self.theme.ansi[8]  # bright black / dark charcoal
        default_fg = self.theme.fg

        # Specific badge color overrides
        wifi_color = self.theme.ansi[10] if self.wifi.connected else self.theme.ansi[1]  # green / red
        ctrl_color = self.theme.ansi[11]  # bright yellow (matches yellow cursor / #ffe08a)
        ctrl_bg = self.theme.ansi[3] if self.ctrl_latch else status_bg

        # Battery color thresholds
        bat_color = self.theme.ansi[10]  # default green
        if self.battery.percent is not None:
            if self.battery.percent < 20:
                bat_color = self.theme.ansi[9]  # bright red
            elif self.battery.percent < 45:
                bat_color = self.theme.ansi[11]  # bright yellow
            elif self.battery.is_charging:
                bat_color = self.theme.ansi[14]  # bright cyan for charging

        # Write each character with appropriate section coloring
        in_ctrl = False
        in_bat = False
        in_wifi = False

        for col, char in enumerate(text):
            fg = default_fg
            bg = status_bg

            # Determine semantic section for per-field color coding
            tail = text[col:]
            if tail.startswith("[CTRL]") or tail.startswith("[^]"):
                in_ctrl = True
            elif in_ctrl and char == "]":
                fg = ctrl_color
                bg = ctrl_bg
                grid._cells[target_row][col] = Cell(char=char, fg=fg, bg=bg)
                in_ctrl = False
                continue

            if in_ctrl:
                fg = ctrl_color
                bg = ctrl_bg
            elif "WiFi:" in text[: col + 5] or (self.wifi.ssid and self.wifi.ssid[:4] in text[: col + 4]):
                fg = wifi_color
            elif "%" in tail[:6] or "Bat:" in text[: col + 4] or "V " in text[: col + 4]:
                fg = bat_color
            elif col < 4:
                # Workspace badge highlight
                fg = self.theme.ansi[13]  # bright magenta / pink

            grid._cells[target_row][col] = Cell(char=char, fg=fg, bg=bg)

        self._dirty = False
        return True
