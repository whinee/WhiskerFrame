"""
Geometric models and rectangle coordinate interfaces (imagesmacker 7.0.0 parity).

Mirror the imagesmacker 7.0.0 ``models.coordinates`` surface in strict parity:
the :class:`XYNamedTuple` / :class:`WHNamedTuple` / :class:`XYXYNamedTuple` /
:class:`XYWHNamedTuple` / :class:`FourXYNamedTuple` view structures, the
:class:`RectangleCoordinates` abstract base class, and the concrete
:class:`XYXY`, :class:`XYWH`, and :class:`FourXY` rectangle representations.
Every representation converts to a canonical bounding box and exposes
:meth:`RectangleCoordinates.anchor_coordinates`, which resolves a two-character
``[lmr][tmb]`` anchor to an ``(x, y)`` pixel using pure integer math (no
floating point, no imaging dependency). Anchor validation is delegated to
:mod:`whiskerframe.anchors`, so the ``[lmr][tmb]`` grammar and default ``"mm"``
are shared with the rest of the library.

This module is pure: it imports no Pillow (or any imaging library) so it can run
on the serial command path without imaging dependencies.
"""

from __future__ import annotations

import abc
from collections.abc import Iterator
from itertools import combinations
from typing import Literal, NamedTuple, TypeAlias, Union

from whiskerframe.anchors import DEFAULT_ANCHOR, Anchor, resolve_anchor

# =========================
# View / output structures
# =========================


class XYNamedTuple(NamedTuple):
    """Two-dimensional point coordinates ``(x, y)``."""

    x: int
    y: int


class WHNamedTuple(NamedTuple):
    """Two-dimensional size dimensions ``(w, h)``."""

    w: int
    h: int


class XYXYNamedTuple(NamedTuple):
    """Bounding box corner coordinates ``(x1, y1, x2, y2)``."""

    x1: int
    y1: int
    x2: int
    y2: int


class XYWHNamedTuple(NamedTuple):
    """Bounding box origin and dimensions ``(x, y, w, h)``."""

    x: int
    y: int
    w: int
    h: int


class FourXYNamedTuple(NamedTuple):
    """Four-vertex corner points defining a quadrilateral."""

    xy1: XYNamedTuple
    xy2: XYNamedTuple
    xy3: XYNamedTuple
    xy4: XYNamedTuple


# =========================
# Base rectangle interface
# =========================


class RectangleCoordinates(metaclass=abc.ABCMeta):
    """
    Abstract coordinate interface for axis-aligned rectangular regions.

    Enable representation-agnostic conversion between the XYXY, XYWH, and
    four-vertex forms and compute anchor points for text and shape placement.
    Concrete subclasses implement :meth:`xyxy`, :meth:`xywh`, and :meth:`as_list`;
    the base class derives every other view (four vertices, width/height, anchor
    point) from the canonical bounding box returned by :meth:`xyxy`. This mirrors
    imagesmacker 7.0.0's ``RectangleCoordinates`` in strict parity.
    """

    coordinates: NamedTuple
    w: int
    h: int

    @abc.abstractmethod
    def xyxy(self) -> XYXYNamedTuple:
        """
        Return the canonical bounding box in ``(x1, y1, x2, y2)`` form.

        Returns:
        `XYXYNamedTuple`: The top-left and bottom-right corner coordinates.

        """
        ...

    @abc.abstractmethod
    def xywh(self) -> XYWHNamedTuple:
        """
        Return the bounding box in ``(x, y, w, h)`` form.

        Returns:
        `XYWHNamedTuple`: The top-left origin and the box dimensions.

        """
        ...

    @abc.abstractmethod
    def as_list(
        self,
    ) -> list[int] | list[NamedTuple] | list[Union[int, NamedTuple]]:
        """
        Return the rectangle coordinates as a list.

        Returns:
        `list[int] | list[NamedTuple] | list[Union[int, NamedTuple]]`: The
        integer coordinates or vertex tuples of the representation.

        """
        ...

    def as_tuple(self) -> tuple:
        """
        Return the rectangle coordinates as a tuple.

        Returns:
        `tuple`: The tuple conversion of :meth:`as_list`.

        """
        return tuple(self.as_list())

    def fourxy(self) -> FourXYNamedTuple:
        """
        Return the four corner vertices of the bounding box.

        Derive the vertices from the canonical bounding box in clockwise order
        starting from the top-left corner.

        Returns:
        `FourXYNamedTuple`: The four corner vertices, clockwise from top-left.

        """
        x1, y1, x2, y2 = self.xyxy()
        return FourXYNamedTuple(
            XYNamedTuple(x1, y1),
            XYNamedTuple(x2, y1),
            XYNamedTuple(x2, y2),
            XYNamedTuple(x1, y2),
        )

    def wh(self) -> WHNamedTuple:
        """
        Return the rectangle dimensions as width and height.

        Returns:
        `WHNamedTuple`: The width and height of the rectangle.

        """
        return WHNamedTuple(self.w, self.h)

    def anchor_coordinates(self, anchor: Anchor = DEFAULT_ANCHOR) -> XY:
        """
        Resolve a two-character anchor to its ``(x, y)`` pixel on the bounding box.

        Validate the anchor against the ``[lmr][tmb]`` grammar, then map the
        horizontal key (``l``/``m``/``r``) to left/center/right and the vertical
        key (``t``/``m``/``b``) to top/middle/bottom of the canonical bounding
        box. The center uses pure integer math (floor division), so the result is
        always an integer pixel and no imaging dependency is required::

            x = {l: x1, m: (x1 + x2) // 2, r: x2}[anchor[0]]
            y = {t: y1, m: (y1 + y2) // 2, b: y2}[anchor[1]]

        Args:
        - anchor (`Anchor`, optional): Two-character anchor specification string. Defaults to `"mm"`.

        Raises:
        - `ValueError`: If the anchor is not two characters or contains an invalid key.

        Returns:
        `XY`: The resolved anchor point as an :class:`XY` with integer coordinates.

        """
        horizontal, vertical = resolve_anchor(anchor)
        x1, y1, x2, y2 = self.xyxy()

        if horizontal == "l":
            x = x1
        elif horizontal == "m":
            x = (x1 + x2) // 2
        else:  # "r"
            x = x2

        if vertical == "t":
            y = y1
        elif vertical == "m":
            y = (y1 + y2) // 2
        else:  # "b"
            y = y2

        return XY(x, y)


# =========================
# Simple coordinate types
# =========================


class XY:
    """A two-dimensional point with non-negative integer coordinates."""

    def __init__(self, x: int, y: int) -> None:
        """
        Initialize a 2D point coordinate.

        Args:
        - x (`int`): Non-negative horizontal coordinate.
        - y (`int`): Non-negative vertical coordinate.

        Raises:
        - `ValueError`: If either ``x`` or ``y`` is negative.

        Returns:
        `None`: This initializer does not return a value.

        """
        if x < 0 or y < 0:
            msg = "Coordinates must be non-negative."
            raise ValueError(msg)
        self.x = x
        self.y = y

    def xy(self) -> XYNamedTuple:
        """
        Return the point coordinates as a named tuple.

        Returns:
        `XYNamedTuple`: The ``(x, y)`` coordinates.

        """
        return XYNamedTuple(self.x, self.y)

    def __iter__(self) -> Iterator[int]:
        """
        Yield the ``x`` and ``y`` coordinates in order.

        Yields:
        `int`: The ``x`` coordinate followed by the ``y`` coordinate.

        """
        return iter((self.x, self.y))


class WH:
    """Two-dimensional dimensions with non-negative width and height."""

    def __init__(self, w: int, h: int) -> None:
        """
        Initialize dimension metrics.

        Args:
        - w (`int`): Non-negative width value.
        - h (`int`): Non-negative height value.

        Raises:
        - `ValueError`: If either ``w`` or ``h`` is negative.

        Returns:
        `None`: This initializer does not return a value.

        """
        if w < 0 or h < 0:
            msg = "Width and height must be non-negative."
            raise ValueError(msg)
        self.w = w
        self.h = h

    def wh(self) -> WHNamedTuple:
        """
        Return the dimensions as a named tuple.

        Returns:
        `WHNamedTuple`: The ``(w, h)`` dimensions.

        """
        return WHNamedTuple(self.w, self.h)

    def __iter__(self) -> Iterator[int]:
        """
        Yield the width and height in order.

        Yields:
        `int`: The width followed by the height.

        """
        return iter((self.w, self.h))


# =========================
# Rectangle implementations
# =========================


class XYXY(RectangleCoordinates):
    """An axis-aligned rectangle defined by two opposing corner coordinates."""

    def __init__(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """
        Initialize the rectangle from top-left and bottom-right corners.

        Args:
        - x1 (`int`): Left coordinate.
        - y1 (`int`): Top coordinate.
        - x2 (`int`): Right coordinate; must be greater than ``x1``.
        - y2 (`int`): Bottom coordinate; must be greater than ``y1``.

        Raises:
        - `ValueError`: If the bounds are degenerate or any coordinate is negative.

        Returns:
        `None`: This initializer does not return a value.

        """
        if x1 >= x2 or y1 >= y2:
            msg = "Invalid rectangle bounds."
            raise ValueError(msg)
        if x1 < 0 or y1 < 0:
            msg = "Coordinates must be non-negative."
            raise ValueError(msg)

        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.w = x2 - x1
        self.h = y2 - y1

    def as_list(self) -> list[int]:
        """
        Return the corner bounds as a four-integer list.

        Returns:
        `list[int]`: The list ``[x1, y1, x2, y2]``.

        """
        return [self.x1, self.y1, self.x2, self.y2]

    def xyxy(self) -> XYXYNamedTuple:
        """
        Return the corner bounds as an ``XYXYNamedTuple``.

        Returns:
        `XYXYNamedTuple`: The ``(x1, y1, x2, y2)`` corner bounds.

        """
        return XYXYNamedTuple(self.x1, self.y1, self.x2, self.y2)

    def xywh(self) -> XYWHNamedTuple:
        """
        Return the origin and dimensions as an ``XYWHNamedTuple``.

        Returns:
        `XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

        """
        return XYWHNamedTuple(self.x1, self.y1, self.w, self.h)


class XYWH(RectangleCoordinates):
    """An axis-aligned rectangle defined by an origin position and dimensions."""

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        """
        Initialize the rectangle from a top-left origin and positive dimensions.

        Args:
        - x (`int`): Left coordinate of the origin.
        - y (`int`): Top coordinate of the origin.
        - w (`int`): Width of the rectangle; must be greater than ``0``.
        - h (`int`): Height of the rectangle; must be greater than ``0``.

        Raises:
        - `ValueError`: If width or height is non-positive, or the origin is negative.

        Returns:
        `None`: This initializer does not return a value.

        """
        if w <= 0 or h <= 0:
            msg = "Width and height must be > 0."
            raise ValueError(msg)
        if x < 0 or y < 0:
            msg = "Coordinates must be non-negative."
            raise ValueError(msg)

        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def as_list(self) -> list[int]:
        """
        Return the origin and dimensions as a four-integer list.

        Returns:
        `list[int]`: The list ``[x, y, w, h]``.

        """
        return [self.x, self.y, self.w, self.h]

    def xyxy(self) -> XYXYNamedTuple:
        """
        Compute the opposing corner bounds as an ``XYXYNamedTuple``.

        Returns:
        `XYXYNamedTuple`: The ``(x, y, x + w, y + h)`` corner bounds.

        """
        return XYXYNamedTuple(self.x, self.y, self.x + self.w, self.y + self.h)

    def xywh(self) -> XYWHNamedTuple:
        """
        Return the origin and dimensions as an ``XYWHNamedTuple``.

        Returns:
        `XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

        """
        return XYWHNamedTuple(self.x, self.y, self.w, self.h)


# =========================
# Four-point rectangle
# =========================


def distances_squared(a: XYNamedTuple, b: XYNamedTuple) -> int:
    """
    Compute the squared Euclidean distance between two points.

    Avoid a floating-point square root so distance comparisons stay exact.

    Args:
    - a (`XYNamedTuple`): First coordinate point.
    - b (`XYNamedTuple`): Second coordinate point.

    Returns:
    `int`: The squared Euclidean distance between the points.

    """
    dx = b.x - a.x
    dy = b.y - a.y
    return dx * dx + dy * dy


class FourXY(RectangleCoordinates):
    """A rectangle defined by four explicit corner vertices."""

    def __init__(
        self,
        xy1: XYNamedTuple,
        xy2: XYNamedTuple,
        xy3: XYNamedTuple,
        xy4: XYNamedTuple,
    ) -> None:
        """
        Initialize the rectangle from four corner vertices.

        Validate that the four points are distinct and form a non-degenerate
        planar rectangle (four equal shortest edges and two equal diagonals).

        Args:
        - xy1 (`XYNamedTuple`): First corner coordinate.
        - xy2 (`XYNamedTuple`): Second corner coordinate.
        - xy3 (`XYNamedTuple`): Third corner coordinate.
        - xy4 (`XYNamedTuple`): Fourth corner coordinate.

        Raises:
        - `ValueError`: If the vertices are degenerate or do not form a rectangle.

        Returns:
        `None`: This initializer does not return a value.

        """
        points = [xy1, xy2, xy3, xy4]

        if len({(p.x, p.y) for p in points}) != 4:
            msg = "Points must be distinct."
            raise ValueError(msg)

        distances = sorted(distances_squared(a, b) for a, b in combinations(points, 2))

        if distances[0] == 0:
            msg = "Degenerate rectangle."
            raise ValueError(msg)

        # The six pairwise squared distances of a rectangle are: two equal short
        # sides, two equal long sides, and two equal diagonals. Sorted, that is
        # [s, s, l, l, d, d] with s <= l and, by the Pythagorean theorem,
        # d == s + l (in squared terms). A square is the special case s == l.
        side_sq, long_sq, diag_sq = distances[0], distances[2], distances[4]
        sides_equal = distances[0] == distances[1]
        longs_equal = distances[2] == distances[3]
        diags_equal = distances[4] == distances[5]
        pythagorean = diag_sq == side_sq + long_sq
        if not (sides_equal and longs_equal and diags_equal and pythagorean):
            msg = "Points do not form a rectangle."
            raise ValueError(msg)

        # For an axis-aligned rectangle, width and height are the bounding-box
        # extents (so orientation is preserved and w != h is handled). side_sq /
        # long_sq above still validate the rectangle shape via the Pythagorean
        # relation; they are not used for w/h to avoid swapping the two axes.
        xs = [pt.x for pt in points]
        ys = [pt.y for pt in points]
        self.w = max(xs) - min(xs)
        self.h = max(ys) - min(ys)
        self.points = (xy1, xy2, xy3, xy4)

    def as_list(self) -> list[NamedTuple]:
        """
        Return the corner points as a list of named tuples.

        Returns:
        `list[NamedTuple]`: The four corner coordinate points.

        """
        return list(self.points)

    def _is_axis_aligned(self) -> bool:
        """
        Report whether the rectangle edges align with the coordinate axes.

        Returns:
        `bool`: ``True`` if the rectangle is axis-aligned, ``False`` otherwise.

        """
        xs = {p.x for p in self.points}
        ys = {p.y for p in self.points}
        return len(xs) == 2 and len(ys) == 2

    def xyxy(self) -> XYXYNamedTuple:
        """
        Return the axis-aligned bounding box corner bounds.

        Raises:
        - `ValueError`: If the rectangle is not axis-aligned.

        Returns:
        `XYXYNamedTuple`: The minimum and maximum ``(x1, y1, x2, y2)`` bounds.

        """
        if not self._is_axis_aligned():
            msg = "Rectangle is not axis-aligned."
            raise ValueError(msg)

        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return XYXYNamedTuple(min(xs), min(ys), max(xs), max(ys))

    def xywh(self) -> XYWHNamedTuple:
        """
        Return the axis-aligned bounding box origin and dimensions.

        Returns:
        `XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

        """
        x1, y1, _, _ = self.xyxy()
        return XYWHNamedTuple(x1, y1, self.w, self.h)

    def fourxy(self) -> FourXYNamedTuple:
        """
        Return the four corner points as a ``FourXYNamedTuple``.

        Returns:
        `FourXYNamedTuple`: The four corner vertices.

        """
        return FourXYNamedTuple(*self.points)


# =========================
# Type aliases
# =========================

coordinates_type_alias: TypeAlias = Literal["XY", "WH"]
"""Discriminator for the simple coordinate types (``XY`` or ``WH``)."""

rectangle_coordinates_type_alias: TypeAlias = Literal["XYXY", "XYWH", "FourXY"]
"""Discriminator for the rectangle representations (``XYXY``/``XYWH``/``FourXY``)."""
