r"""
Publish a `BatteryReading` to a userspace ``power_supply``-class mirror.

Writes a kernel ``power_supply``-formatted ``uevent`` file plus a JSON status
file under ``/run/battery_monitor/`` so the operating system and any tooling can
read the UPS Module 3S as if it were a battery. The ``uevent`` file uses the
exact ``POWER_SUPPLY_*`` key/value grammar the kernel emits for a real battery
(name, type, capacity, status, and voltage/current in micro-units), which is the
format ``upower``/``udev`` consumers expect.

Kernel-native alternative (documented, not required here): binding the mainline
``ina2xx`` hwmon driver via a device-tree overlay would expose the INA219 in
``/sys/class/hwmon`` and, with a battery ``power_supply`` shim, register a true
in-kernel ``power_supply`` device. That path needs a device-tree overlay and a
compatible kernel; this userspace publisher works on the stock image with no
kernel rebuild, so it is the robust default. See ``README.md``.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from .battery import (
    STATUS_CHARGING,
    STATUS_DISCHARGING,
    STATUS_FULL,
    STATUS_NOT_CHARGING,
    BatteryReading,
)
from .debug import tracepoint

__all__ = [
    "DEFAULT_RUN_DIR",
    "PowerSupplyPublisher",
    "format_uevent",
]

DEFAULT_RUN_DIR: Path = Path("/run/battery_monitor")
"""Default tmpfs directory for the ``uevent`` and ``status.json`` mirror files."""

# Map internal status strings to the kernel POWER_SUPPLY_STATUS enumerants. The
# battery module already uses the kernel spellings, so this is an identity guard
# that also documents the accepted set.
_STATUS_ENUM: dict[str, str] = {
    STATUS_CHARGING: STATUS_CHARGING,
    STATUS_DISCHARGING: STATUS_DISCHARGING,
    STATUS_FULL: STATUS_FULL,
    STATUS_NOT_CHARGING: STATUS_NOT_CHARGING,
}


def format_uevent(reading: BatteryReading, name: str) -> str:
    r"""
    Format a `BatteryReading` as a kernel ``power_supply`` ``uevent`` body.

    Emits the ``POWER_SUPPLY_*`` key/value lines a real battery exposes: name,
    ``Battery`` type, present flag, integer capacity, status, and voltage/current
    converted to the kernel's micro-unit convention (microvolts / microamps).

    Args:
    - reading (`BatteryReading`): The resolved battery measurement to publish.
    - name (`str`): ``POWER_SUPPLY_NAME`` value (the logical battery name).

    Returns:
    `str`: The newline-terminated ``uevent`` file body.

    """
    status = _STATUS_ENUM.get(reading.status, STATUS_NOT_CHARGING)
    voltage_uv = round(reading.voltage * 1_000_000)
    current_ua = round(reading.current * 1_000)  # mA -> uA.
    lines = (
        f"POWER_SUPPLY_NAME={name}",
        "POWER_SUPPLY_TYPE=Battery",
        "POWER_SUPPLY_PRESENT=1",
        f"POWER_SUPPLY_CAPACITY={reading.percent}",
        f"POWER_SUPPLY_STATUS={status}",
        f"POWER_SUPPLY_VOLTAGE_NOW={voltage_uv}",
        f"POWER_SUPPLY_CURRENT_NOW={current_ua}",
    )
    return "\n".join(lines) + "\n"


class PowerSupplyPublisher:
    r"""
    Publish battery readings to the userspace ``power_supply`` mirror.

    Owns the run directory and atomically rewrites the ``uevent`` and
    ``status.json`` files on each poll so a reader never observes a torn file.
    Writes are confined to ``run_dir`` (the systemd unit grants
    ``ReadWritePaths=/run/battery_monitor``).

    Attributes:
    - name (`str`): ``POWER_SUPPLY_NAME`` published for the battery.
    - run_dir (`Path`): Directory holding ``uevent`` and ``status.json``.

    """

    def __init__(
        self,
        name: str = "cyberdeck_ups",
        run_dir: Path = DEFAULT_RUN_DIR,
    ) -> None:
        r"""
        Initialize the publisher for a battery name and run directory.

        Args:
        - name (`str`, optional): ``POWER_SUPPLY_NAME`` value. Defaults to ``"cyberdeck_ups"``.
        - run_dir (`Path`, optional): Mirror directory. Defaults to `DEFAULT_RUN_DIR`.

        """
        self.name = name
        self.run_dir = run_dir

    @property
    def uevent_path(self) -> Path:
        r"""
        Return the path to the ``uevent`` mirror file.

        Returns:
        `Path`: ``<run_dir>/uevent``.

        """
        return self.run_dir / "uevent"

    @property
    def status_path(self) -> Path:
        r"""
        Return the path to the ``status.json`` mirror file.

        Returns:
        `Path`: ``<run_dir>/status.json``.

        """
        return self.run_dir / "status.json"

    def ensure_dir(self) -> None:
        r"""
        Create the run directory if it does not already exist.

        Idempotent: an existing directory is left untouched. The systemd
        ``tmpfiles.d`` entry normally creates it, but this makes a manual run
        self-sufficient.

        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, path: Path, text: str) -> None:
        r"""
        Write ``text`` to ``path`` atomically via a temp file and ``rename``.

        Writes to a temporary file in the same directory, flushes and ``fsync``s
        it, then renames over the target so readers see either the old or the new
        content, never a partial write.

        Args:
        - path (`Path`): Destination file path.
        - text (`str`): Full file contents to write.

        """
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except OSError:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def publish(self, reading: BatteryReading) -> None:
        r"""
        Write the ``uevent`` and ``status.json`` files for a reading.

        Ensures the run directory exists, then atomically rewrites the kernel
        ``uevent`` mirror and a JSON status snapshot (voltage, current, percent,
        status, name).

        Args:
        - reading (`BatteryReading`): The resolved battery measurement to publish.

        Raises:
        - `OSError`: If the run directory or mirror files cannot be written.

        """
        self.ensure_dir()
        tracepoint(
            "power_supply.publish",
            percent=reading.percent,
            status=reading.status,
            uevent_path=self.uevent_path,
        )
        self._atomic_write(self.uevent_path, format_uevent(reading, self.name))
        self._last_reading = reading
        status_doc = {
            "name": self.name,
            "voltage_v": round(reading.voltage, 4),
            "current_ma": round(reading.current, 3),
            "percent": reading.percent,
            "status": reading.status,
            "updated_at": time.time(),
            "fresh": True,
        }
        self._atomic_write(self.status_path, json.dumps(status_doc, indent=2) + "\n")

    def mark_stale(self, reason: str) -> None:
        r"""
        Flag the published status as stale during an I2C read failure.

        Rewrite ``status.json`` with ``fresh=False`` and the error ``reason`` so a
        reader can tell the daemon is retrying rather than that the pack genuinely
        froze. The last good electrical values are kept for context; the ``uevent``
        mirror is left untouched (the kernel keeps the last known capacity).

        Args:
        - reason (`str`): Human-readable description of the read failure.

        """
        self.ensure_dir()
        last = getattr(self, "_last_reading", None)
        status_doc = {
            "name": self.name,
            "voltage_v": round(last.voltage, 4) if last else None,
            "current_ma": round(last.current, 3) if last else None,
            "percent": last.percent if last else None,
            "status": last.status if last else "Unknown",
            "updated_at": time.time(),
            "fresh": False,
            "stale_reason": reason,
        }
        self._atomic_write(self.status_path, json.dumps(status_doc, indent=2) + "\n")
