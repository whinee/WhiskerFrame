"""
WhiskerFrame core status bar module.

Re-exports the pure status bar models and rendering primitives for terminal
status telemetry (workspace, Wi-Fi, battery from INA219, Ctrl latch state).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add pi/ to sys.path to access the terminal package implementation
_PI_DIR = Path(__file__).resolve().parent.parent / "pi"
if str(_PI_DIR) not in sys.path:
    sys.path.insert(0, str(_PI_DIR))

from terminal.status_bar import (  # noqa: E402  # type: ignore[import-not-found]
    BatteryInfo,
    StatusBar,
    WifiInfo,
    read_battery_telemetry,
    read_wifi_telemetry,
)

__all__ = [
    "BatteryInfo",
    "StatusBar",
    "WifiInfo",
    "read_battery_telemetry",
    "read_wifi_telemetry",
]
