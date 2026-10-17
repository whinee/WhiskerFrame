"""
Configurable status bar subsystem for the WhiskerFrame cyberdeck terminal.

Inspired by i3status/i3bar modular configuration and read-only data providers,
adapted to CYD hardware constraints.

Displays independently configurable modules (workspace, Wi-Fi, battery from INA219,
mobile/LTE, disk usage, host-link health, current time/date, CardKB sticky Ctrl latch)
driven by context-sensitive profiles (login, root, neko, default) with access control.

Anti-Flicker Architecture:
The status bar writes strictly to its designated row in the terminal Grid (row 0
or bottom row). When Grid.diff(prev_grid) computes the screen update:
- Unchanged terminal rows yield 0 draw runs.
- If status telemetry has not changed, 0 draw runs are emitted for the status row.
- When telemetry changes, only modified cells are coalesced into a single compact DRAW_CELLS command.
- The full panel is never cleared, completely eliminating visual redraw flicker.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .grid import Cell, Grid
from .theme import Theme, load_theme

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "BatteryInfo",
    "DiskInfo",
    "HostLinkInfo",
    "MobileInfo",
    "StatusBar",
    "WifiInfo",
    "read_battery_telemetry",
    "read_disk_telemetry",
    "read_mobile_telemetry",
    "read_wifi_telemetry",
]

_DEFAULT_BATTERY_DIR = Path("/run/battery_monitor")
_DEFAULT_STATUS_BG = 0x24E9  # Off-blurple derived from blurple bg 0x18C5


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


@dataclass(frozen=True)
class MobileInfo:
    """Resolved mobile/LTE signal telemetry."""

    signal: int | None
    connected: bool
    carrier: str | None


@dataclass(frozen=True)
class DiskInfo:
    """Resolved disk usage telemetry."""

    percent: int
    free_gb: float
    total_gb: float


@dataclass(frozen=True)
class HostLinkInfo:
    """Resolved host-link / heartbeat health status."""

    status: str  # "OK", "SYNC", "DEGRADED"
    last_seen_age_s: float


def read_battery_telemetry(run_dir: Path | str = _DEFAULT_BATTERY_DIR) -> BatteryInfo:
    """
    Read battery telemetry from /run/battery_monitor/status.json or uevent mirror.

    Safe and total: returns BatteryInfo(None, None, "Unknown") on any missing file
    or parse error. Never raises an exception.
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
                        volt_val = round(int(line.split("=", 1)[1]) / 1_000_000.0, 2)
                    elif line.startswith("POWER_SUPPLY_STATUS="):
                        st_val = line.split("=", 1)[1]
            return BatteryInfo(percent=pct_val, voltage=volt_val, status=st_val)
        except (OSError, ValueError, TypeError):
            pass

    return BatteryInfo(percent=None, voltage=None, status="Unknown")


def read_wifi_telemetry() -> WifiInfo:
    """Read active Wi-Fi telemetry using nmcli or cache file with safe fallback."""
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
                    sig = _read_active_wifi_signal()
                    return WifiInfo(ssid=active_conn, signal=sig, connected=True)
    except (OSError, subprocess.SubprocessError):
        pass

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


def read_mobile_telemetry() -> MobileInfo:
    """Read mobile/LTE signal telemetry with safe fallback if absent."""
    modem_status = Path("/run/modem/status.json")
    if modem_status.is_file():
        try:
            with open(modem_status, encoding="utf-8") as f:
                data = json.load(f)
            return MobileInfo(
                signal=int(data.get("signal", 0)),
                connected=bool(data.get("connected", False)),
                carrier=str(data.get("carrier", "LTE")),
            )
        except (OSError, ValueError):
            pass
    return MobileInfo(signal=None, connected=False, carrier=None)


def read_disk_telemetry(path: str = "/") -> DiskInfo:
    """Read disk usage telemetry safely using shutil.disk_usage."""
    try:
        usage = shutil.disk_usage(path)
        total_gb = round(usage.total / (1024 ** 3), 1)
        free_gb = round(usage.free / (1024 ** 3), 1)
        used_pct = int((usage.used / usage.total) * 100) if usage.total > 0 else 0
        return DiskInfo(percent=used_pct, free_gb=free_gb, total_gb=total_gb)
    except OSError:
        return DiskInfo(percent=0, free_gb=0.0, total_gb=0.0)


class StatusBar:
    """
    Configurable status bar maintaining system telemetry and rendering to a Grid.

    Supports multiple modules, ordering, profile-based access control (login, root, neko),
    and responsive geometry adaptation.
    """

    def __init__(
        self,
        theme: Theme | None = None,
        workspace: str | int = 1,
        position: str = "top",
        row: int | None = None,
        enabled: bool = True,
        profile: str = "default",
        user: str = "root",
        config: dict[str, Any] | None = None,
    ) -> None:
        self.theme: Theme = theme if theme is not None else load_theme(None)
        self.workspace: str | int = workspace
        self.position: str = position.lower()
        self.row: int | None = row
        self.enabled: bool = enabled
        self.profile: str = profile.lower()
        self.user: str = user
        self._config = config or {}

        # Resolve status bar theme background from config or default off-blurple
        sb_cfg = self._config.get("terminal", {}).get("status_bar", {}) if isinstance(self._config, dict) else {}
        raw_bg = sb_cfg.get("theme_bg", _DEFAULT_STATUS_BG)
        self.status_bg: int = int(raw_bg, 0) if isinstance(raw_bg, str) else int(raw_bg)

        self.wifi: WifiInfo = WifiInfo(ssid=None, signal=None, connected=False)
        self.mobile: MobileInfo = MobileInfo(signal=None, connected=False, carrier=None)
        self.battery: BatteryInfo = BatteryInfo(percent=None, voltage=None, status="Unknown")
        self.disk: DiskInfo = DiskInfo(percent=0, free_gb=0.0, total_gb=0.0)
        self.host_link: HostLinkInfo = HostLinkInfo(status="OK", last_seen_age_s=0.0)
        self.ctrl_latch: bool = False

        self._dirty: bool = True
        self._last_formatted: str = ""

    @property
    def dirty(self) -> bool:
        return self._dirty

    def set_workspace(self, ws: str | int) -> bool:
        if self.workspace != ws:
            self.workspace = ws
            self._dirty = True
            return True
        return False

    def set_wifi(self, ssid: str | None, signal: int | None = None, connected: bool = True) -> bool:
        new_info = WifiInfo(ssid=ssid, signal=signal, connected=connected)
        if self.wifi != new_info:
            self.wifi = new_info
            self._dirty = True
            return True
        return False

    def set_battery(self, percent: int | None, voltage: float | None = None, status: str = "Discharging") -> bool:
        new_info = BatteryInfo(percent=percent, voltage=voltage, status=status)
        if self.battery != new_info:
            self.battery = new_info
            self._dirty = True
            return True
        return False

    def set_ctrl_latch(self, armed: bool) -> bool:
        if self.ctrl_latch != armed:
            self.ctrl_latch = armed
            self._dirty = True
            return True
        return False

    def refresh_telemetry(self, battery_dir: Path | str = _DEFAULT_BATTERY_DIR) -> bool:
        changed = False
        new_bat = read_battery_telemetry(battery_dir)
        if self.battery != new_bat:
            self.battery = new_bat
            changed = True

        new_wifi = read_wifi_telemetry()
        if self.wifi != new_wifi:
            self.wifi = new_wifi
            changed = True

        new_mobile = read_mobile_telemetry()
        if self.mobile != new_mobile:
            self.mobile = new_mobile
            changed = True

        new_disk = read_disk_telemetry()
        if self.disk != new_disk:
            self.disk = new_disk
            changed = True

        if changed:
            self._dirty = True
        return changed

    def target_row(self, grid: Grid) -> int:
        if self.row is not None:
            return max(0, min(self.row, grid.rows - 1))
        if self.position == "bottom":
            return max(0, grid.rows - 1)
        return 0

    def _get_profile_modules(self) -> list[str]:
        """Resolve modules for active profile with access control enforcement."""
        terminal_cfg = self._config.get("terminal", {}) if isinstance(self._config, dict) else {}
        sb_cfg = terminal_cfg.get("status_bar", {}) if isinstance(terminal_cfg, dict) else {}
        profiles = sb_cfg.get("profiles", {}) if isinstance(sb_cfg, dict) else {}

        profile_data = profiles.get(self.profile) or profiles.get("default") or {}
        modules = profile_data.get("order") or profile_data.get("modules") or ["workspace", "wifi", "battery", "time", "ctrl_latch"]

        # Access control enforcement: non-root users or login profile cannot access privileged modules
        is_root = (self.user == "root" and self.profile != "login")
        privileged_modules = {"disk"}

        filtered = []
        for mod in modules:
            if mod in privileged_modules and not is_root:
                continue
            if self.profile == "login" and mod in {"workspace", "ctrl_latch"}:
                continue
            filtered.append(mod)
        return filtered

    def format_status(self, cols: int) -> str:
        """
        Format modules into a single-line compact status string strictly constrained to cols width,
        adhering to the active profile's module order and geometry constraints.
        """
        modules = self._get_profile_modules()
        parts: list[str] = []

        for mod in modules:
            if mod == "workspace":
                parts.append(f"[{self.workspace}]")
            elif mod == "wifi":
                if self.wifi.connected and self.wifi.ssid:
                    sig = f"{self.wifi.signal}%" if self.wifi.signal is not None else ""
                    if cols >= 48:
                        ssid_disp = self.wifi.ssid[:10] + "~" if len(self.wifi.ssid) > 11 else self.wifi.ssid
                        parts.append(f"WiFi:{ssid_disp} {sig}".strip())
                    elif cols >= 35:
                        ssid_disp = self.wifi.ssid[:6] + "~" if len(self.wifi.ssid) > 7 else self.wifi.ssid
                        parts.append(f"{ssid_disp} {sig}".strip())
                    else:
                        parts.append(self.wifi.ssid[:5])
                else:
                    parts.append("WiFi:--" if cols >= 35 else "WIFI")
            elif mod == "battery":
                if self.battery.percent is not None:
                    pct = f"{self.battery.percent}%"
                    chg = "+" if self.battery.is_charging else ""
                    if cols >= 48 and self.battery.voltage is not None:
                        parts.append(f"Bat:{self.battery.voltage:.1f}V {pct}{chg}")
                    elif cols >= 35 and self.battery.voltage is not None:
                        parts.append(f"{self.battery.voltage:.1f}V {pct}{chg}")
                    else:
                        parts.append(f"{pct}{chg}")
                else:
                    parts.append("Bat:--" if cols >= 35 else "BAT")
            elif mod == "disk":
                if cols >= 48:
                    parts.append(f"Disk:{self.disk.percent}%({self.disk.free_gb}G)")
                elif cols >= 35:
                    parts.append(f"Dsk:{self.disk.percent}%")
            elif mod == "host_link":
                parts.append("LINK:OK" if cols >= 48 else "OK")
            elif mod == "time":
                now_str = datetime.datetime.now().strftime("%H:%M" if cols < 48 else "%b %d %H:%M")
                parts.append(now_str)
            elif mod == "ctrl_latch":
                if self.ctrl_latch:
                    parts.append("[CTRL]" if cols >= 35 else "[^]")

        # Assemble with separators
        raw = "  ".join(parts)
        if len(raw) > cols:
            # Drop least essential parts from the middle if width exceeded
            raw = " | ".join(parts[:2])

        padded = raw[:cols].ljust(cols, " ")
        self._last_formatted = padded
        return padded

    def render_to_grid(self, grid: Grid, row: int | None = None) -> bool:
        if not self.enabled:
            return False

        target_row = self.target_row(grid) if row is None else max(0, min(row, grid.rows - 1))
        text = self.format_status(grid.cols)

        status_bg = self.status_bg
        default_fg = self.theme.fg

        wifi_color = self.theme.ansi[10] if self.wifi.connected else self.theme.ansi[1]
        ctrl_color = self.theme.ansi[11]
        ctrl_bg = self.theme.ansi[3] if self.ctrl_latch else status_bg

        bat_color = self.theme.ansi[10]
        if self.battery.percent is not None:
            if self.battery.percent < 20:
                bat_color = self.theme.ansi[9]
            elif self.battery.percent < 45:
                bat_color = self.theme.ansi[11]
            elif self.battery.is_charging:
                bat_color = self.theme.ansi[14]

        in_ctrl = False
        for col, char in enumerate(text):
            fg = default_fg
            bg = status_bg

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
                fg = self.theme.ansi[13]

            grid._cells[target_row][col] = Cell(char=char, fg=fg, bg=bg)

        self._dirty = False
        return True
