r"""
Convert INA219 bus voltage into a pack percentage and charge status.

Maps the measured bus voltage of the configured multi-cell pack (default 3S,
9.0-12.6 V) onto a 0-100 % state of charge by a linear
``voltage_empty..voltage_full`` interpolation with clamping, and derives a
``power_supply``-style status (Charging / Discharging / Full / Not charging)
from the sign of the measured current. This module is pure: it holds no I2C
state and takes measurements as plain floats, so its conversion logic is unit-
and property-testable without hardware.
"""

from __future__ import annotations

from dataclasses import dataclass

from .debug import tracepoint

__all__ = [
    "STATUS_CHARGING",
    "STATUS_DISCHARGING",
    "STATUS_FULL",
    "STATUS_NOT_CHARGING",
    "BatteryReading",
    "PackConfig",
    "derive_status",
    "read_to_reading",
    "voltage_to_percent",
]

# power_supply POWER_SUPPLY_STATUS enumerants used by the kernel class.
STATUS_CHARGING: str = "Charging"
STATUS_DISCHARGING: str = "Discharging"
STATUS_FULL: str = "Full"
STATUS_NOT_CHARGING: str = "Not charging"

# A pack is treated as "Full" at or above this percentage.
_FULL_THRESHOLD_PERCENT: float = 99.0

# Current magnitude (mA) below which the pack is considered idle (Not charging).
_IDLE_CURRENT_MA: float = 5.0


@dataclass(frozen=True)
class PackConfig:
    r"""
    Battery pack parameters used to convert voltage into a percentage.

    Holds the endpoints of the linear voltage-to-percent map for the configured
    pack. Frozen so a resolved configuration cannot mutate mid-run.

    Attributes:
    - voltage_full (`float`): Bus voltage (V) treated as 100 %.
    - voltage_empty (`float`): Bus voltage (V) treated as 0 %.

    """

    voltage_full: float = 12.6
    voltage_empty: float = 9.0


@dataclass(frozen=True)
class BatteryReading:
    r"""
    A single resolved battery measurement.

    Bundles the raw electrical measurement with the derived state of charge and
    ``power_supply`` status for one poll cycle.

    Attributes:
    - voltage (`float`): Bus voltage in volts.
    - current (`float`): Current in milliamps (signed; sign convention per wiring).
    - percent (`int`): State of charge, clamped to ``0..100``.
    - status (`str`): One of the ``STATUS_*`` ``power_supply`` enumerants.

    """

    voltage: float
    current: float
    percent: int
    status: str


def voltage_to_percent(voltage: float, pack: PackConfig) -> int:
    r"""
    Convert a bus voltage to a clamped 0-100 state of charge.

    Linearly interpolates between ``pack.voltage_empty`` (0 %) and
    ``pack.voltage_full`` (100 %) and clamps the result into ``0..100``. A pack
    whose endpoints are equal or inverted degrades safely to ``0``.

    Args:
    - voltage (`float`): Measured bus voltage in volts.
    - pack (`PackConfig`): Pack voltage endpoints.

    Returns:
    `int`: State of charge as an integer percentage in ``0..100``.

    """
    span = pack.voltage_full - pack.voltage_empty
    if span <= 0:
        tracepoint("battery.percent", voltage=voltage, percent=0)
        return 0
    fraction = (voltage - pack.voltage_empty) / span
    percent = max(0, min(100, round(fraction * 100)))
    tracepoint("battery.percent", voltage=voltage, percent=percent)
    return percent


def derive_status(current_ma: float, percent: int) -> str:
    r"""
    Derive a ``power_supply`` status from current sign and state of charge.

    Reports ``Full`` at or above the full threshold, ``Charging`` when current
    indicates charge into the pack, ``Discharging`` when it flows out, and
    ``Not charging`` when the current is within the idle deadband.

    Args:
    - current_ma (`float`): Signed current in milliamps (positive = charging).
    - percent (`int`): State of charge in ``0..100``.

    Returns:
    `str`: One of the ``STATUS_*`` enumerants.

    """
    if percent >= _FULL_THRESHOLD_PERCENT:
        status = STATUS_FULL
    elif current_ma > _IDLE_CURRENT_MA:
        status = STATUS_CHARGING
    elif current_ma < -_IDLE_CURRENT_MA:
        status = STATUS_DISCHARGING
    else:
        status = STATUS_NOT_CHARGING
    tracepoint("battery.status", current_ma=current_ma, status=status)
    return status


def read_to_reading(
    voltage: float,
    current_ma: float,
    pack: PackConfig,
) -> BatteryReading:
    r"""
    Build a `BatteryReading` from a voltage/current measurement.

    Combines `voltage_to_percent` and `derive_status` into the single reading the
    publisher and daemon consume.

    Args:
    - voltage (`float`): Bus voltage in volts.
    - current_ma (`float`): Signed current in milliamps.
    - pack (`PackConfig`): Pack voltage endpoints.

    Returns:
    `BatteryReading`: The resolved reading (voltage, current, percent, status).

    """
    percent = voltage_to_percent(voltage, pack)
    status = derive_status(current_ma, percent)
    return BatteryReading(
        voltage=voltage,
        current=current_ma,
        percent=percent,
        status=status,
    )
