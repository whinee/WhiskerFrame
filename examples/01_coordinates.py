"""
Example: rectangle coordinate representations and anchor resolution (Req 10.1).

Construct the three :mod:`whiskerframe.coordinates` rectangle representations --
:class:`XYXY`, :class:`XYWH`, and :class:`FourXY` -- over the same 100x100 region,
show that each converts to the identical canonical bounding box (``xyxy`` /
``xywh`` / ``fourxy`` / ``wh``), and resolve a handful of ``[lmr][tmb]`` anchors
to their ``(x, y)`` pixels via
:meth:`RectangleCoordinates.anchor_coordinates`. Everything here is pure integer
math -- no Pillow, no serial port -- so the script runs anywhere the package
imports.

Run it with ``python examples/01_coordinates.py`` (or ``just examples``).
"""

from __future__ import annotations

from whiskerframe import XYWH, XYXY, FourXY
from whiskerframe.anchors import Anchor
from whiskerframe.coordinates import RectangleCoordinates, XYNamedTuple

# A shared 100x100 region expressed three different ways: top-left (20, 10),
# bottom-right (120, 110). FourXY validates four equal edges, so a square keeps
# all three representations describing one identical bounding box.
_X1, _Y1, _X2, _Y2 = 20, 10, 120, 110

# A representative subset of the nine anchors, one per corner plus the center.
_ANCHORS: tuple[Anchor, ...] = ("lt", "rt", "mm", "lb", "rb")


def build_rectangles() -> dict[str, RectangleCoordinates]:
    """
    Build the same region as ``XYXY``, ``XYWH``, and ``FourXY``.

    All three describe the region with top-left ``(20, 10)`` and bottom-right
    ``(120, 110)``, so they should share one canonical bounding box.

    Returns:
    `dict[str, RectangleCoordinates]`: The three representations keyed by name.

    """
    return {
        "XYXY": XYXY(_X1, _Y1, _X2, _Y2),
        "XYWH": XYWH(_X1, _Y1, _X2 - _X1, _Y2 - _Y1),
        "FourXY": FourXY(
            XYNamedTuple(_X1, _Y1),
            XYNamedTuple(_X2, _Y1),
            XYNamedTuple(_X2, _Y2),
            XYNamedTuple(_X1, _Y2),
        ),
    }


def show_conversions(name: str, rect: RectangleCoordinates) -> None:
    """
    Print the canonical conversions for one rectangle representation.

    Args:
    - name (`str`): Human-readable representation name.
    - rect (`RectangleCoordinates`): Rectangle to convert.

    Returns:
    `None`: This function only prints.

    """
    print(f"{name}:")
    print(f"  xyxy   -> {tuple(rect.xyxy())}")
    print(f"  xywh   -> {tuple(rect.xywh())}")
    print(f"  wh     -> {tuple(rect.wh())}")
    print(f"  fourxy -> {tuple(tuple(v) for v in rect.fourxy())}")


def show_anchors(rect: RectangleCoordinates) -> None:
    """
    Print resolved anchor pixels for a subset of ``[lmr][tmb]`` anchors.

    Args:
    - rect (`RectangleCoordinates`): Rectangle whose anchors are resolved.

    Returns:
    `None`: This function only prints.

    """
    print("anchor_coordinates:")
    for anchor in _ANCHORS:
        point = rect.anchor_coordinates(anchor)
        print(f"  {anchor} -> {tuple(point)}")


def main() -> None:
    """
    Build the rectangles, show conversions, then resolve anchors.

    Returns:
    `None`: This function only prints.

    """
    rectangles = build_rectangles()

    print("== Coordinate conversions (all three describe one 100x100 region) ==")
    for name, rect in rectangles.items():
        show_conversions(name, rect)

    print("\n== Anchor resolution (on the XYXY region) ==")
    show_anchors(rectangles["XYXY"])


if __name__ == "__main__":
    main()
