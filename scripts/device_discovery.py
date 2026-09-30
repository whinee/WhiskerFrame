"""
Device discovery: enumerate USB/serial devices and diff against a baseline.

The `Device_Discovery` workflow identifies which serial port belongs to the
newly connected CYD (an ESP32 + ILI9341 board) versus the Pi's own built-in
serial, by comparing the current device set against a `Baseline` captured with
no USB-serial device connected (Req 5.1-5.4).

The module separates two concerns for testability:

- **OS enumeration** (`enumerate_devices`, `capture_baseline`) shells out to
  ``lsusb`` and globs ``/dev/ttyUSB*``, ``/dev/ttyACM*``, and
  ``/dev/serial/by-id/`` to snapshot the machine's current devices.
- **Pure diff/report** (`diff_devices`, `report`) is a side-effect-free set
  difference over device snapshots. It never touches the OS, so it can be
  property-tested directly (Property 9).

A `Baseline` is valid input to a diff only if it was captured with no USB-serial
device connected (Req 5.2); the module surfaces this as a constraint on the
snapshot passed to `diff_devices`, not as a mandated capture step.

``/dev/serial/by-id/`` symlinks are preferred in the human-facing report because
they are stable across reboots, unlike the ``/dev/ttyUSB*`` / ``/dev/ttyACM*``
node numbers which the kernel may reassign.
"""

from __future__ import annotations

import glob
import subprocess
from typing import NamedTuple

from debug import tracepoint

__all__ = [
    "BY_ID_DIR",
    "TTY_GLOBS",
    "DeviceDiff",
    "DeviceSnapshot",
    "DiscoveryReport",
    "capture_baseline",
    "diff_devices",
    "enumerate_devices",
    "report",
]

BY_ID_DIR: str = "/dev/serial/by-id/"
"""Directory of stable, reboot-invariant serial device symlinks."""

TTY_GLOBS: tuple[str, ...] = ("/dev/ttyUSB*", "/dev/ttyACM*")
"""Glob patterns for USB-serial character devices under ``/dev``."""


class DeviceSnapshot(NamedTuple):
    """
    Immutable snapshot of enumerated USB and serial devices.

    A snapshot records the three enumeration sources independently so the diff
    can compare like with like and the report can prefer the stable
    ``by-id`` symlinks. Each field is stored as a `frozenset` so snapshots are
    hashable and set differences are order-independent.

    Attributes:
    - usb (`frozenset[str]`): ``lsusb`` device identity lines.
    - tty (`frozenset[str]`): ``/dev/ttyUSB*`` and ``/dev/ttyACM*`` node paths.
    - by_id (`frozenset[str]`): ``/dev/serial/by-id/*`` stable symlink paths.

    """

    usb: frozenset[str]
    tty: frozenset[str]
    by_id: frozenset[str]


class DeviceDiff(NamedTuple):
    """
    Set difference between a current snapshot and a baseline snapshot.

    ``added`` holds devices present now but absent from the baseline (the
    devices that appeared when the CYD was connected); ``removed`` holds devices
    absent now but present in the baseline. Each field mirrors the three
    enumeration sources of `DeviceSnapshot`.

    Attributes:
    - added (`DeviceSnapshot`): Devices present now but absent from the baseline.
    - removed (`DeviceSnapshot`): Devices present in the baseline but absent now.

    """

    added: DeviceSnapshot
    removed: DeviceSnapshot


class DiscoveryReport(NamedTuple):
    """
    Human-facing result identifying the CYD versus the Pi serial ports.

    ``cyd_ports`` are the serial nodes that newly appeared relative to the
    baseline (the CYD), preferring stable ``by-id`` symlinks; ``pi_ports`` are
    the serial nodes present in the baseline (the Pi's built-in serial).

    Attributes:
    - cyd_ports (`tuple[str, ...]`): Serial ports attributed to the connected CYD.
    - pi_ports (`tuple[str, ...]`): Serial ports attributed to the Pi's built-in serial.
    - diff (`DeviceDiff`): The underlying baseline diff the report was derived from.

    """

    cyd_ports: tuple[str, ...]
    pi_ports: tuple[str, ...]
    diff: DeviceDiff


def _run_lsusb() -> frozenset[str]:
    """
    Enumerate USB devices via ``lsusb``.

    Runs ``lsusb`` and returns each non-empty output line as a device identity.
    If ``lsusb`` is unavailable or exits non-zero, an empty set is returned so
    enumeration degrades gracefully rather than raising.

    Returns:
    `frozenset[str]`: One entry per ``lsusb`` output line.

    """
    try:
        completed = subprocess.run(
            ["lsusb"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return frozenset()
    if completed.returncode != 0:
        return frozenset()
    return frozenset(
        line.strip() for line in completed.stdout.splitlines() if line.strip()
    )


def _glob_tty() -> frozenset[str]:
    """
    Enumerate USB-serial character-device nodes.

    Globs each pattern in `TTY_GLOBS` and unions the matches.

    Returns:
    `frozenset[str]`: Matching ``/dev/ttyUSB*`` and ``/dev/ttyACM*`` paths.

    """
    paths: set[str] = set()
    for pattern in TTY_GLOBS:
        paths.update(glob.glob(pattern))
    return frozenset(paths)


def _glob_by_id() -> frozenset[str]:
    """
    Enumerate stable serial symlinks under ``/dev/serial/by-id/``.

    Returns:
    `frozenset[str]`: Matching ``/dev/serial/by-id/*`` symlink paths.

    """
    return frozenset(glob.glob(BY_ID_DIR + "*"))


def enumerate_devices() -> DeviceSnapshot:
    """
    Snapshot the machine's current USB and serial devices.

    Enumerates all three sources (``lsusb``, the ``tty`` globs, and the
    ``by-id`` symlink directory) and returns them as a single `DeviceSnapshot`
    (Req 5.1). This function performs OS I/O and is kept separate from the pure
    `diff_devices` for testability.

    Returns:
    `DeviceSnapshot`: The current device set across all enumeration sources.

    """
    snapshot = DeviceSnapshot(
        usb=_run_lsusb(),
        tty=_glob_tty(),
        by_id=_glob_by_id(),
    )
    tracepoint(
        "discovery.enumerate",
        usb_count=len(snapshot.usb),
        tty_count=len(snapshot.tty),
        by_id_count=len(snapshot.by_id),
    )
    return snapshot


def capture_baseline() -> DeviceSnapshot:
    """
    Capture a baseline device snapshot.

    A baseline is only valid input to a diff if it is captured with no
    USB-serial device connected (Req 5.2); this helper does not itself verify
    that precondition, it simply snapshots the current device set for the caller
    to record while the CYD is unplugged.

    Returns:
    `DeviceSnapshot`: The device set to be used as a diff baseline.

    """
    return enumerate_devices()


def diff_devices(baseline: DeviceSnapshot, current: DeviceSnapshot) -> DeviceDiff:
    """
    Compute the set difference of a current snapshot against a baseline.

    Pure, side-effect-free set arithmetic per enumeration source: ``added`` is
    ``current - baseline`` and ``removed`` is ``baseline - current`` for each of
    ``usb``, ``tty``, and ``by_id`` (Req 5.3, Property 9). No OS access.

    Args:
    - baseline (`DeviceSnapshot`): Devices recorded with no USB-serial connected.
    - current (`DeviceSnapshot`): Devices enumerated with the CYD connected.

    Returns:
    `DeviceDiff`: The added and removed device sets across all sources.

    """
    diff = DeviceDiff(
        added=DeviceSnapshot(
            usb=current.usb - baseline.usb,
            tty=current.tty - baseline.tty,
            by_id=current.by_id - baseline.by_id,
        ),
        removed=DeviceSnapshot(
            usb=baseline.usb - current.usb,
            tty=baseline.tty - current.tty,
            by_id=baseline.by_id - current.by_id,
        ),
    )
    tracepoint(
        "discovery.diff",
        added=len(diff.added.tty) + len(diff.added.by_id),
        removed=len(diff.removed.tty) + len(diff.removed.by_id),
    )
    return diff


def _preferred_ports(snapshot: DeviceSnapshot) -> tuple[str, ...]:
    """
    Select the preferred serial ports from a snapshot.

    Prefers the reboot-stable ``by-id`` symlinks; falls back to the ``tty``
    node paths only when no ``by-id`` symlink is present. Results are sorted for
    deterministic reporting.

    Args:
    - snapshot (`DeviceSnapshot`): Snapshot (typically a diff's added/removed set).

    Returns:
    `tuple[str, ...]`: Preferred serial port paths, sorted.

    """
    if snapshot.by_id:
        return tuple(sorted(snapshot.by_id))
    return tuple(sorted(snapshot.tty))


def report(baseline: DeviceSnapshot, current: DeviceSnapshot) -> DiscoveryReport:
    """
    Identify the CYD serial port versus the Pi serial from a baseline diff.

    Diffs ``current`` against ``baseline`` and attributes the newly appeared
    serial nodes to the CYD and the baseline-present serial nodes to the Pi's
    built-in serial (Req 5.4). Both port lists prefer stable ``by-id`` symlinks
    over ``tty`` node paths. Pure with respect to the OS; it only calls
    `diff_devices`.

    Args:
    - baseline (`DeviceSnapshot`): Devices recorded with no USB-serial connected.
    - current (`DeviceSnapshot`): Devices enumerated with the CYD connected.

    Returns:
    `DiscoveryReport`: The CYD and Pi serial ports plus the underlying diff.

    """
    diff = diff_devices(baseline, current)
    cyd_ports = _preferred_ports(diff.added)
    pi_ports = _preferred_ports(baseline)
    tracepoint(
        "discovery.report",
        cyd_ports=len(cyd_ports),
        pi_ports=len(pi_ports),
    )
    return DiscoveryReport(
        cyd_ports=cyd_ports,
        pi_ports=pi_ports,
        diff=diff,
    )
