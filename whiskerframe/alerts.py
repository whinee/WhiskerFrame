"""
whiskerframe.alerts: Critical system state alert monitoring & profile-governed dispatch (REQ-INP-07).

Evaluates telemetry conditions (battery, thermals, memory pressure) and determines
appropriate audio, haptic, and visual alert actions governed by the active
sensory profile (REQ-ENV-04) and cognitive sensory overload toggle (REQ-INP-08).

Thresholds:
- Battery: <= 5% CRITICAL (emergency shutdown threshold), <= 15% WARNING (low battery)
- Thermal: >= 80°C CRITICAL (emergency thermal throttling), >= 75°C WARNING
- Memory: < 50MB CRITICAL (earlyoom danger zone), < 100MB WARNING
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

__all__ = [
    "AlertCategory",
    "AlertEvent",
    "AlertSeverity",
    "SystemMetrics",
    "check_system_health",
    "evaluate_alerts",
]


class AlertSeverity(StrEnum):
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertCategory(StrEnum):
    BATTERY = "battery"
    THERMAL = "thermal"
    MEMORY = "memory"


@dataclass(frozen=True)
class SystemMetrics:
    """Current snapshot of critical cyberdeck system metrics."""

    battery_percent: float
    thermal_celsius: float
    available_ram_mb: float


@dataclass(frozen=True)
class AlertEvent:
    """A generated system state alert and its dispatch attributes."""

    category: AlertCategory
    severity: AlertSeverity
    message: str
    audible: bool
    haptic: bool
    visual: bool
    suppressed_by_profile: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "audible": self.audible,
            "haptic": self.haptic,
            "visual": self.visual,
            "suppressed_by_profile": self.suppressed_by_profile,
        }


def _get_sensory_state() -> dict[str, Any]:
    """Load active sensory profile state from disk or default to office."""
    override = os.environ.get("WHISKERFRAME_SENSORY_STATE")
    candidates = [
        Path(override) if override else None,
        Path("/run/whiskerframe/sensory_profile.json"),
        Path("/tmp/whiskerframe/sensory_profile.json"),  # noqa: S108
        Path("/tmp/sensory_profile.json"),  # noqa: S108
    ]
    for c in candidates:
        if c and c.is_file():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                pass
    return {
        "profile": "office",
        "buzzer_volume": 25,
        "haptics_enabled": True,
        "alerts_audible": True,
        "overload_active": False,
    }


def _check_battery_alert(
    pct: float,
    audible: bool,
    haptic: bool,
    suppressed: bool,
) -> AlertEvent | None:
    if pct <= 5.0:
        return AlertEvent(
            category=AlertCategory.BATTERY,
            severity=AlertSeverity.CRITICAL,
            message=f"Battery critical: {pct:.1f}% (shutdown imminent)",
            audible=audible,
            haptic=haptic,
            visual=True,
            suppressed_by_profile=suppressed,
        )
    if pct <= 15.0:
        return AlertEvent(
            category=AlertCategory.BATTERY,
            severity=AlertSeverity.WARNING,
            message=f"Battery low: {pct:.1f}%",
            audible=audible,
            haptic=haptic,
            visual=True,
            suppressed_by_profile=suppressed,
        )
    return None


def _check_thermal_alert(
    temp_c: float,
    audible: bool,
    haptic: bool,
    suppressed: bool,
) -> AlertEvent | None:
    if temp_c >= 80.0:
        return AlertEvent(
            category=AlertCategory.THERMAL,
            severity=AlertSeverity.CRITICAL,
            message=f"Emergency thermal threshold exceeded: {temp_c:.1f}°C",
            audible=audible,
            haptic=haptic,
            visual=True,
            suppressed_by_profile=suppressed,
        )
    if temp_c >= 75.0:
        return AlertEvent(
            category=AlertCategory.THERMAL,
            severity=AlertSeverity.WARNING,
            message=f"Thermal warning: {temp_c:.1f}°C",
            audible=audible,
            haptic=haptic,
            visual=True,
            suppressed_by_profile=suppressed,
        )
    return None


def _check_memory_alert(
    ram_mb: float,
    audible: bool,
    haptic: bool,
    suppressed: bool,
) -> AlertEvent | None:
    if ram_mb < 50.0:
        return AlertEvent(
            category=AlertCategory.MEMORY,
            severity=AlertSeverity.CRITICAL,
            message=f"Memory critical: {ram_mb:.1f}MB available (earlyoom risk)",
            audible=audible,
            haptic=haptic,
            visual=True,
            suppressed_by_profile=suppressed,
        )
    if ram_mb < 100.0:
        return AlertEvent(
            category=AlertCategory.MEMORY,
            severity=AlertSeverity.WARNING,
            message=f"Memory low: {ram_mb:.1f}MB available",
            audible=audible,
            haptic=haptic,
            visual=True,
            suppressed_by_profile=suppressed,
        )
    return None


def evaluate_alerts(
    metrics: SystemMetrics,
    sensory_state: dict[str, Any] | None = None,
) -> list[AlertEvent]:
    """
    Evaluate system metrics and return all active alert events.

    Audible and haptic dispatches are strictly filtered through the active
    sensory profile (REQ-ENV-04) and cognitive sensory overload toggle (REQ-INP-08).
    """
    state = sensory_state if sensory_state is not None else _get_sensory_state()
    overload_active = bool(state.get("overload_active", False))
    alerts_audible = bool(state.get("alerts_audible", True)) and not overload_active
    haptics_enabled = bool(state.get("haptics_enabled", True)) and not overload_active
    suppressed = overload_active or not alerts_audible

    events: list[AlertEvent] = []
    bat = _check_battery_alert(
        metrics.battery_percent,
        alerts_audible,
        haptics_enabled,
        suppressed,
    )
    if bat is not None:
        events.append(bat)

    thm = _check_thermal_alert(
        metrics.thermal_celsius,
        alerts_audible,
        haptics_enabled,
        suppressed,
    )
    if thm is not None:
        events.append(thm)

    mem = _check_memory_alert(
        metrics.available_ram_mb,
        alerts_audible,
        haptics_enabled,
        suppressed,
    )
    if mem is not None:
        events.append(mem)

    return events


def _read_live_battery() -> float:
    for cand in (
        Path("/run/battery_monitor/status.json"),
        Path("/tmp/battery_monitor/status.json"),  # noqa: S108
    ):
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
                return float(data.get("percent", 100.0))
            except (OSError, ValueError):
                pass
    return 100.0


def _read_live_thermal() -> float:
    thermal_file = Path("/sys/class/thermal/thermal_zone0/temp")
    if thermal_file.is_file():
        try:
            raw = thermal_file.read_text(encoding="utf-8").strip()
            return float(raw) / 1000.0
        except (OSError, ValueError):
            pass
    return 45.0


def _read_live_memory() -> float:
    meminfo_file = Path("/proc/meminfo")
    if meminfo_file.is_file():
        try:
            for line in meminfo_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    return float(parts[1]) / 1024.0
        except (OSError, ValueError):
            pass
    return 250.0


def check_system_health() -> tuple[list[AlertEvent], SystemMetrics]:
    """Sample live hardware sysfs / procfs telemetry and evaluate alerts."""
    metrics = SystemMetrics(
        battery_percent=_read_live_battery(),
        thermal_celsius=_read_live_thermal(),
        available_ram_mb=_read_live_memory(),
    )
    return evaluate_alerts(metrics), metrics
