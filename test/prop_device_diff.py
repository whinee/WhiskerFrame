"""
Property test for `Device_Discovery` diff correctness (Req 5.3).

**Property 9: Device diff equals the set difference against the baseline**

**Validates: Requirements 5.3**

For any baseline `DeviceSnapshot` and any current `DeviceSnapshot`, the diff
computed by `diff_devices` reports, per enumeration source (``usb``, ``tty``,
``by_id``), exactly the devices present in the current set but absent from the
baseline as ``added``, and those present in the baseline but absent from the
current set as ``removed`` -- i.e. the plain set differences
``current - baseline`` and ``baseline - current``.

The script is pure (no hardware, no OS enumeration): it drives the
side-effect-free `diff_devices` with hypothesis-generated device-id sets, runs
as ``uv run python test/prop_device_diff.py``, prints ``PASS`` on success, and
exits non-zero on the first falsifying example.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from device_discovery import DeviceSnapshot, diff_devices

device_ids = st.frozensets(st.text(min_size=1, max_size=8), max_size=6)


snapshots = st.builds(
    DeviceSnapshot,
    usb=device_ids,
    tty=device_ids,
    by_id=device_ids,
)


@settings(max_examples=300)
@given(baseline=snapshots, current=snapshots)
def check_diff_is_set_difference(
    baseline: DeviceSnapshot,
    current: DeviceSnapshot,
) -> None:
    """
    Assert the diff equals the per-source set differences (Property 9).

    Args:
    - baseline (`DeviceSnapshot`): Devices recorded with no USB-serial connected.
    - current (`DeviceSnapshot`): Devices enumerated with the CYD connected.

    Raises:
    - `AssertionError`: If any source's added/removed set is not the set
      difference of the corresponding current/baseline fields.

    Returns:
    `None`: This check returns nothing when the diff is correct.

    """
    diff = diff_devices(baseline, current)

    assert diff.added.usb == current.usb - baseline.usb
    assert diff.added.tty == current.tty - baseline.tty
    assert diff.added.by_id == current.by_id - baseline.by_id

    assert diff.removed.usb == baseline.usb - current.usb
    assert diff.removed.tty == baseline.tty - current.tty
    assert diff.removed.by_id == baseline.by_id - current.by_id


def main() -> None:
    """
    Run the Property 9 check and report success.

    Raises:
    - `AssertionError`: If hypothesis finds a falsifying example.

    Returns:
    `None`: This entry point returns nothing.

    """
    check_diff_is_set_difference()
    print("PASS")


if __name__ == "__main__":
    main()
