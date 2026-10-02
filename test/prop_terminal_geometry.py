"""
Property/unit test for the CYD terminal grid geometry.

**Validates: Requirements (cyd-terminal design: Resizable terminal)**

Assert that :class:`whiskerframe.terminal.TerminalGeometry.for_font_size` derives
the documented column/row counts and cell sizes for font sizes 1-3 on the fixed
320x240 panel (size 1 -> 53x30, size 2 -> 26x15, size 3 -> 17x10), and that cols
and rows never overflow the panel for any font size in the metrics table.

The script is pure (no hardware, no Pillow), runs as
``uv run python test/prop_terminal_geometry.py``, prints ``PASS`` on success, and
exits non-zero on the first mismatch.
"""

from __future__ import annotations

import sys

from whiskerframe.metrics import FONT_METRICS
from whiskerframe.terminal import DISPLAY_HEIGHT, DISPLAY_WIDTH, TerminalGeometry

_EXPECTED: dict[int, tuple[int, int, int, int]] = {
    # font_size: (cols, rows, cell_w, cell_h)
    1: (53, 30, 6, 8),
    2: (26, 15, 12, 16),
    3: (17, 10, 18, 24),
}


def check_expected() -> None:
    """
    Assert the documented geometry for font sizes 1-3.

    Raises:
    - `AssertionError`: If any size's geometry differs from the expected tuple.

    Returns:
    `None`: Returns nothing when every size matches.

    """
    for font_size, expected in _EXPECTED.items():
        geo = TerminalGeometry.for_font_size(font_size)
        actual = (geo.cols, geo.rows, geo.cell_w, geo.cell_h)
        assert actual == expected, f"size {font_size}: {actual} != {expected}"


def check_no_overflow() -> None:
    """
    Assert the grid never overflows the panel for any metrics size.

    Raises:
    - `AssertionError`: If a grid's pixel extent exceeds the panel.

    Returns:
    `None`: Returns nothing when every size fits.

    """
    for font_size in FONT_METRICS:
        geo = TerminalGeometry.for_font_size(font_size)
        assert geo.cols * geo.cell_w <= DISPLAY_WIDTH, f"width overflow at {font_size}"
        assert (
            geo.rows * geo.cell_h <= DISPLAY_HEIGHT
        ), f"height overflow at {font_size}"


def main() -> None:
    """
    Run the geometry checks and report the outcome.

    Returns:
    `None`: Exits ``1`` on failure; prints ``PASS`` and exits ``0`` otherwise.

    """
    try:
        check_expected()
        check_no_overflow()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
