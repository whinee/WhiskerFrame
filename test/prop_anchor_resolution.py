"""
Property test for anchor resolution over rectangle coordinates.

**Property 4: Anchor resolution matches the imagesmacker model**

*For any* rectangle (expressed as XYXY or the equivalent XYWH) and *any* of the
nine ``[lmr][tmb]`` anchors, ``RectangleCoordinates.anchor_coordinates(anchor)``
returns the pixel given by the horizontal key mapping to left/center/right and
the vertical key mapping to top/middle/bottom of the canonical bounding box::

    x = {l: x1, m: (x1 + x2) // 2, r: x2}[anchor[0]]
    y = {t: y1, m: (y1 + y2) // 2, b: y2}[anchor[1]]

The rectangle is Hypothesis-generated with ``x1 < x2`` and ``y1 < y2`` inside the
``uint16`` range, and the XYWH form built from the same bounds must resolve to the
identical point (representation independence). The script is pure (no hardware, no
Pillow), runs as ``uv run python test/prop_anchor_resolution.py``, prints ``PASS``
on success, and exits non-zero on the first falsifying example.

**Validates: Requirements 3.1, 3.4, 8.1, 8.2**
"""

from __future__ import annotations

import sys

from hypothesis import given, settings
from hypothesis import strategies as st

from whiskerframe.anchors import Anchor
from whiskerframe.coordinates import XYWH, XYXY

UINT16_MAX: int = 0xFFFF

ANCHORS: tuple[Anchor, ...] = (
    "lt",
    "mt",
    "rt",
    "lm",
    "mm",
    "rm",
    "lb",
    "mb",
    "rb",
)


def expected_point(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    anchor: Anchor,
) -> tuple[int, int]:
    """
    Return the analytic ``(x, y)`` for an anchor over the bounding box.

    Args:
    - x1 (`int`): Left bound.
    - y1 (`int`): Top bound.
    - x2 (`int`): Right bound.
    - y2 (`int`): Bottom bound.
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor.

    Returns:
    `tuple[int, int]`: The expected resolved anchor pixel.

    """
    x_map: dict[str, int] = {"l": x1, "m": (x1 + x2) // 2, "r": x2}
    y_map: dict[str, int] = {"t": y1, "m": (y1 + y2) // 2, "b": y2}
    return x_map[anchor[0]], y_map[anchor[1]]


@settings(max_examples=400)
@given(
    x1=st.integers(min_value=0, max_value=UINT16_MAX - 1),
    y1=st.integers(min_value=0, max_value=UINT16_MAX - 1),
    dx=st.integers(min_value=1, max_value=UINT16_MAX),
    dy=st.integers(min_value=1, max_value=UINT16_MAX),
    anchor=st.sampled_from(ANCHORS),
)
def test_anchor_resolution(x1: int, y1: int, dx: int, dy: int, anchor: Anchor) -> None:
    """
    Assert both XYXY and XYWH resolve an anchor to the analytic point.

    Args:
    - x1 (`int`): Left bound.
    - y1 (`int`): Top bound.
    - dx (`int`): Positive width offset producing ``x2 = x1 + dx``.
    - dy (`int`): Positive height offset producing ``y2 = y1 + dy``.
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor under test.

    Raises:
    - `AssertionError`: If either representation mismatches the analytic point.

    Returns:
    `None`: This property returns nothing when it holds.

    """
    x2 = min(x1 + dx, UINT16_MAX)
    y2 = min(y1 + dy, UINT16_MAX)
    # min() clamps to uint16 range; the +1 guards keep x1 < x2 and y1 < y2.
    if x2 <= x1:
        x2 = x1 + 1
    if y2 <= y1:
        y2 = y1 + 1

    expected_x, expected_y = expected_point(x1, y1, x2, y2, anchor)

    xyxy = XYXY(x1, y1, x2, y2)
    point_xyxy = xyxy.anchor_coordinates(anchor)
    assert (
        point_xyxy.x == expected_x
    ), f"XYXY {anchor}: x {point_xyxy.x} != {expected_x}"
    assert (
        point_xyxy.y == expected_y
    ), f"XYXY {anchor}: y {point_xyxy.y} != {expected_y}"

    xywh = XYWH(x1, y1, x2 - x1, y2 - y1)
    point_xywh = xywh.anchor_coordinates(anchor)
    assert (
        point_xywh.x == expected_x
    ), f"XYWH {anchor}: x {point_xywh.x} != {expected_x}"
    assert (
        point_xywh.y == expected_y
    ), f"XYWH {anchor}: y {point_xywh.y} != {expected_y}"


def main() -> None:
    """
    Run the anchor-resolution property and report success.

    Returns:
    `None`: This entry point returns nothing.

    """
    test_anchor_resolution()
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
