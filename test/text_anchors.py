"""
Anchor-resolution and round-trip test for single-line ``DRAW_TEXT`` (Req 9.1).

Build a ``DRAW_TEXT`` command for each of the nine ``[lmr][tmb]`` anchors over a
known rectangle and assert two things per anchor:

1. The resolved ``(x, y)`` equals the analytically expected anchor point derived
   directly from the imagesmacker 7.0.0 model (Req 3.1, 3.4): the horizontal key
   maps ``l -> x1``, ``m -> (x1 + x2) // 2``, ``r -> x2`` and the vertical key
   maps ``t -> y1``, ``m -> (y1 + y2) // 2``, ``b -> y2``.
2. ``serialize`` followed by ``decode`` round-trips to an equal ``DrawText``
   (Req 1.1).

The script is pure (no hardware, no Pillow), runs as ``python test/text_anchors.py``,
prints ``PASS`` on success, and exits non-zero on the first failed assertion.
"""

from __future__ import annotations

from whiskerframe import XYXY, CommandBuilder, DrawText
from whiskerframe.anchors import Anchor
from whiskerframe.protocol import decode, serialize

RECT_X1: int = 0
RECT_Y1: int = 0
RECT_X2: int = 100
RECT_Y2: int = 40

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


def expected_point(anchor: Anchor) -> tuple[int, int]:
    """
    Return the analytically expected ``(x, y)`` for an anchor over the rectangle.

    Args:
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor.

    Returns:
    `tuple[int, int]`: The expected resolved anchor pixel.

    """
    x_map: dict[str, int] = {
        "l": RECT_X1,
        "m": (RECT_X1 + RECT_X2) // 2,
        "r": RECT_X2,
    }
    y_map: dict[str, int] = {
        "t": RECT_Y1,
        "m": (RECT_Y1 + RECT_Y2) // 2,
        "b": RECT_Y2,
    }
    return x_map[anchor[0]], y_map[anchor[1]]


def check_anchor(builder: CommandBuilder, anchor: Anchor) -> None:
    """
    Assert resolved placement and byte round-trip for a single anchor.

    Args:
    - builder (`CommandBuilder`): Builder used to construct the command.
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor under test.

    Raises:
    - `AssertionError`: If the resolved point or the round-trip mismatches.

    Returns:
    `None`: This check returns nothing when the anchor is valid.

    """
    rect = XYXY(RECT_X1, RECT_Y1, RECT_X2, RECT_Y2)
    command = builder.draw_text(rect, "hi", anchor=anchor)

    expected_x, expected_y = expected_point(anchor)
    assert command.x == expected_x, f"{anchor}: x {command.x} != {expected_x}"
    assert command.y == expected_y, f"{anchor}: y {command.y} != {expected_y}"

    decoded = decode(serialize(command))
    assert isinstance(decoded, DrawText), f"{anchor}: decoded {type(decoded).__name__}"
    assert decoded == command, f"{anchor}: round-trip {decoded!r} != {command!r}"


def main() -> None:
    """
    Run the anchor checks for all nine anchors and report success.

    Raises:
    - `AssertionError`: If any anchor check fails.

    Returns:
    `None`: This entry point returns nothing.

    """
    builder = CommandBuilder()
    for anchor in ANCHORS:
        check_anchor(builder, anchor)
    print("PASS")


if __name__ == "__main__":
    main()
