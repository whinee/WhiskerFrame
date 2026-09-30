r"""
Railguarded battery-monitor daemon for the cyberdeck UPS Module 3S.

Loads the reproducible ``ups:`` configuration from ``.whiskerframe.yaml`` (via
``scripts/config.py``, with fallbacks matching the live-verified hardware),
opens the INA219, and polls it on a fixed interval. Each cycle it converts the
bus voltage to a pack percentage/status and publishes a ``power_supply`` mirror
under ``/run/battery_monitor/``. Logging goes to stdout/stderr, which systemd's
journald captures (``journalctl -u battery-monitor``).

Railguards:
- A transient I2C error never crashes the loop; it is logged and retried with a
  bounded exponential backoff.
- At or below the critical threshold the daemon logs ``CRITICAL``. It triggers a
  clean shutdown when the ``auto_shutdown`` config flag is true, which is now the
  default (a clean poweroff at 5% protects the pack); set it ``false`` to disable.
- The I2C bus is read-only apart from the INA219's one-time calibration write.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .battery import PackConfig, read_to_reading
from .debug import tracepoint
from .ina219 import INA219, INA219Error
from .power_supply import PowerSupplyPublisher

__all__ = [
    "DaemonConfig",
    "load_daemon_config",
    "log",
    "main",
    "run",
]

# Backoff bounds for transient I2C errors (seconds).
_BACKOFF_START_S: float = 1.0
_BACKOFF_MAX_S: float = 30.0


def _load_yaml_config() -> dict[str, Any]:
    r"""
    Load ``.whiskerframe.yaml`` via ``scripts/config.py`` with a safe fallback.

    On the Pi, ``scripts/`` sits beside ``pi/`` under the deploy root, so its
    parent is added to ``sys.path`` to reuse the project's ``load_yaml_config``.
    If the module or file is unavailable, an empty mapping is returned so the
    daemon falls back entirely to the verified hardware defaults.

    Returns:
    `dict[str, Any]`: The parsed configuration mapping (empty on any failure).

    """
    scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from config import load_yaml_config  # type: ignore[import-not-found]
    except ImportError:
        return {}
    loaded = load_yaml_config()
    return loaded if isinstance(loaded, dict) else {}


@dataclass(frozen=True)
class DaemonConfig:
    r"""
    Resolved daemon configuration.

    Bundles the hardware, pack, and behavioral settings resolved from
    ``.whiskerframe.yaml`` (``ups:`` block) with fallbacks matching the
    live-verified INA219 3S build.

    Attributes:
    - i2c_bus (`int`): I2C bus number for ``/dev/i2c-N``.
    - i2c_address (`int`): INA219 slave address.
    - pack (`PackConfig`): Pack voltage endpoints for the percent map.
    - poll_interval_s (`float`): Seconds between polls.
    - low_percent (`int`): Warning threshold (log ``WARNING`` at/below).
    - critical_percent (`int`): Critical threshold (log ``CRITICAL`` at/below).
    - auto_shutdown (`bool`): Whether to power off at the critical threshold.
    - power_supply_name (`str`): ``POWER_SUPPLY_NAME`` published for the battery.

    """

    i2c_bus: int = 1
    i2c_address: int = 0x41
    pack: PackConfig = field(default_factory=PackConfig)
    poll_interval_s: float = 10.0
    low_percent: int = 15
    critical_percent: int = 5
    auto_shutdown: bool = True
    power_supply_name: str = "cyberdeck_ups"


def _as_int(value: Any, default: int) -> int:
    r"""
    Coerce a config value to ``int``, falling back on any failure.

    Args:
    - value (`Any`): Raw config value (may be ``None``, ``str``, ``int``).
    - default (`int`): Value used when coercion fails.

    Returns:
    `int`: The coerced integer or the default.

    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    r"""
    Coerce a config value to ``float``, falling back on any failure.

    Args:
    - value (`Any`): Raw config value.
    - default (`float`): Value used when coercion fails.

    Returns:
    `float`: The coerced float or the default.

    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_daemon_config() -> DaemonConfig:
    r"""
    Resolve the daemon configuration from ``.whiskerframe.yaml``.

    Reads the ``ups:`` block and maps each key onto a `DaemonConfig` field, using
    the live-verified hardware facts as fallbacks for any missing key so a fresh
    checkout still runs. Extra daemon keys (``poll_interval_seconds``,
    ``auto_shutdown``, ``power_supply_name``) are read from the same block.

    Returns:
    `DaemonConfig`: The fully resolved configuration.

    """
    ups: dict[str, Any] = _load_yaml_config().get("ups", {}) or {}
    pack = PackConfig(
        voltage_full=_as_float(ups.get("voltage_full"), 12.6),
        voltage_empty=_as_float(ups.get("voltage_empty"), 9.0),
    )
    config = DaemonConfig(
        i2c_bus=_as_int(ups.get("i2c_bus"), 1),
        i2c_address=_as_int(ups.get("i2c_address"), 0x41),
        pack=pack,
        poll_interval_s=_as_float(ups.get("poll_interval_seconds"), 10.0),
        low_percent=_as_int(ups.get("low_battery_percent"), 15),
        critical_percent=_as_int(ups.get("critical_percent"), 5),
        auto_shutdown=bool(ups.get("auto_shutdown", True)),
        power_supply_name=str(ups.get("power_supply_name", "cyberdeck_ups")),
    )
    tracepoint(
        "daemon.config",
        i2c_address=hex(config.i2c_address),
        poll_interval_s=config.poll_interval_s,
        auto_shutdown=config.auto_shutdown,
        critical_percent=config.critical_percent,
    )
    return config


def log(level: str, message: str) -> None:
    r"""
    Emit a single journald-friendly log line.

    Writes ``LEVEL: message`` to stdout (or stderr for ``ERROR``/``CRITICAL``) so
    systemd's journald captures it with sensible stream separation. No timestamp
    is added; journald timestamps each line.

    Args:
    - level (`str`): Severity label (e.g. ``INFO``, ``WARNING``, ``CRITICAL``).
    - message (`str`): The message body.

    """
    stream = sys.stderr if level in {"ERROR", "CRITICAL"} else sys.stdout
    print(f"{level}: {message}", file=stream, flush=True)


def _trigger_shutdown() -> None:
    r"""
    Request a clean system poweroff.

    Invoked only when ``auto_shutdown`` is enabled and the pack is at/below the
    critical threshold. Uses ``systemctl poweroff`` as an argument vector (no
    shell). A failure is logged but never raised, so the daemon stays alive to
    keep publishing.

    """
    log("CRITICAL", "auto_shutdown enabled: requesting clean poweroff")
    try:
        subprocess.run(("systemctl", "poweroff"), check=False, timeout=30)  # noqa: S607
    except (OSError, subprocess.SubprocessError) as err:
        log("ERROR", f"poweroff request failed: {err}")


def _check_thresholds(percent: int, config: DaemonConfig) -> None:
    r"""
    Log low/critical warnings and optionally trigger auto-shutdown.

    Args:
    - percent (`int`): Current state of charge in ``0..100``.
    - config (`DaemonConfig`): Resolved thresholds and the ``auto_shutdown`` flag.

    """
    level = _threshold_level(percent, config)
    tracepoint("daemon.threshold", percent=percent, level=level)
    if level == "critical":
        log(
            "CRITICAL",
            f"battery at {percent}% (<= {config.critical_percent}% critical)",
        )
        if config.auto_shutdown:
            _trigger_shutdown()
    elif level == "low":
        log("WARNING", f"battery at {percent}% (<= {config.low_percent}% low)")


def _threshold_level(percent: int, config: DaemonConfig) -> str:
    r"""
    Classify a state of charge against the low/critical thresholds.

    Args:
    - percent (`int`): Current state of charge in ``0..100``.
    - config (`DaemonConfig`): Resolved low/critical thresholds.

    Returns:
    `str`: ``"critical"``, ``"low"``, or ``"ok"``.

    """
    if percent <= config.critical_percent:
        return "critical"
    if percent <= config.low_percent:
        return "low"
    return "ok"


def _poll_once(
    device: INA219,
    publisher: PowerSupplyPublisher,
    config: DaemonConfig,
) -> None:
    r"""
    Perform one measurement, publish it, and evaluate thresholds.

    Args:
    - device (`INA219`): Open, calibrated INA219 driver.
    - publisher (`PowerSupplyPublisher`): Userspace ``power_supply`` publisher.
    - config (`DaemonConfig`): Resolved configuration.

    Raises:
    - `INA219Error`: If a bus read fails (handled by the caller's backoff).

    """
    voltage = device.bus_voltage_v()
    current = device.current_ma()
    reading = read_to_reading(voltage, current, config.pack)
    tracepoint("daemon.poll", percent=reading.percent, status=reading.status)
    publisher.publish(reading)
    log(
        "INFO",
        f"{reading.percent}% {reading.status} "
        f"{reading.voltage:.2f}V {reading.current:.1f}mA",
    )
    _check_thresholds(reading.percent, config)


def run(config: DaemonConfig, iterations: int | None = None) -> int:
    r"""
    Run the railguarded poll loop.

    Opens and calibrates the INA219, then polls every ``poll_interval_s`` seconds.
    A transient `INA219Error` is logged and retried with bounded exponential
    backoff instead of crashing the loop; a successful poll resets the backoff.

    Args:
    - config (`DaemonConfig`): Resolved configuration.
    - iterations (`int | None`, optional): Stop after this many successful polls (for tests). Defaults to unbounded.

    Returns:
    `int`: Process exit code (``0`` on a clean bounded run).

    """
    publisher = PowerSupplyPublisher(config.power_supply_name)
    device = INA219(bus=config.i2c_bus, address=config.i2c_address)
    device.open()
    device.calibrate()
    log(
        "INFO",
        f"battery-monitor started (bus {config.i2c_bus}, addr {config.i2c_address:#04x})",
    )
    backoff = _BACKOFF_START_S
    completed = 0
    try:
        while iterations is None or completed < iterations:
            try:
                _poll_once(device, publisher, config)
                backoff = _BACKOFF_START_S
                completed += 1
            except INA219Error as err:
                log("ERROR", f"I2C read failed, retrying in {backoff:.0f}s: {err}")
                tracepoint("daemon.backoff", seconds=backoff)
                time.sleep(backoff)
                backoff = min(_BACKOFF_MAX_S, backoff * 2)
                continue
            if iterations is None or completed < iterations:
                time.sleep(config.poll_interval_s)
    finally:
        device.close()
    return 0


def main() -> int:
    r"""
    Entry point: load configuration and run the daemon loop.

    Returns:
    `int`: Process exit code.

    """
    return run(load_daemon_config())


if __name__ == "__main__":
    raise SystemExit(main())
