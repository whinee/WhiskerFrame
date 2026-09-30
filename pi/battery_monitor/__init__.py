"""
Battery-monitor daemon for the cyberdeck UPS Module 3S (INA219 over I2C).

Reads the UPS Module 3S's Texas Instruments INA219 power monitor on ``/dev/i2c-1``
and publishes the pack state to the kernel ``power_supply`` class (via a robust
userspace mirror under ``/run/battery_monitor/``) so the operating system sees a
battery. The package is stdlib-only on the I2C path so it runs inside the minimal
uv-managed Pi venv (which ships only ``pydantic`` / ``pyserial``).

Modules:
- `ina219`: pure-stdlib INA219 I2C driver.
- `battery`: bus-voltage -> percent/status conversion for the configured pack.
- `power_supply`: userspace ``power_supply``-class publisher.
- `daemon`: railguarded poll loop wired for systemd/journald.
"""

from __future__ import annotations

__all__ = [
    "__version__",
]

__version__ = "0.1.0"
