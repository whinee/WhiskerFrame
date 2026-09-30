Module whiskerframe.coordinates
===============================
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

Variables
---------

`coordinates_type_alias: TypeAlias`
:   Discriminator for the simple coordinate types (``XY`` or ``WH``).

`rectangle_coordinates_type_alias: TypeAlias`
:   Discriminator for the rectangle representations (``XYXY``/``XYWH``/``FourXY``).

Functions
---------

`distances_squared(a: XYNamedTuple, b: XYNamedTuple) ‑> int`
:   Compute the squared Euclidean distance between two points.
    
    Avoid a floating-point square root so distance comparisons stay exact.
    
    Args:
    - a (`XYNamedTuple`): First coordinate point.
    - b (`XYNamedTuple`): Second coordinate point.
    
    Returns:
    `int`: The squared Euclidean distance between the points.

Classes
-------

`FourXY(xy1: XYNamedTuple, xy2: XYNamedTuple, xy3: XYNamedTuple, xy4: XYNamedTuple)`
:   A rectangle defined by four explicit corner vertices.
    
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

    ### Ancestors (in MRO)

    * whiskerframe.coordinates.RectangleCoordinates

    ### Methods

    `as_list(self) ‑> list[typing.NamedTuple]`
    :   Return the corner points as a list of named tuples.
        
        Returns:
        `list[NamedTuple]`: The four corner coordinate points.

    `fourxy(self) ‑> whiskerframe.coordinates.FourXYNamedTuple`
    :   Return the four corner points as a ``FourXYNamedTuple``.
        
        Returns:
        `FourXYNamedTuple`: The four corner vertices.

    `xywh(self) ‑> whiskerframe.coordinates.XYWHNamedTuple`
    :   Return the axis-aligned bounding box origin and dimensions.
        
        Returns:
        `XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

    `xyxy(self) ‑> whiskerframe.coordinates.XYXYNamedTuple`
    :   Return the axis-aligned bounding box corner bounds.
        
        Raises:
        - `ValueError`: If the rectangle is not axis-aligned.
        
        Returns:
        `XYXYNamedTuple`: The minimum and maximum ``(x1, y1, x2, y2)`` bounds.

`FourXYNamedTuple(xy1: ForwardRef('XYNamedTuple'), xy2: ForwardRef('XYNamedTuple'), xy3: ForwardRef('XYNamedTuple'), xy4: ForwardRef('XYNamedTuple'))`
:   Four-vertex corner points defining a quadrilateral.

    ### Ancestors (in MRO)

    * builtins.tuple

    ### Instance variables

    `xy1: whiskerframe.coordinates.XYNamedTuple`
    :   Alias for field number 0

    `xy2: whiskerframe.coordinates.XYNamedTuple`
    :   Alias for field number 1

    `xy3: whiskerframe.coordinates.XYNamedTuple`
    :   Alias for field number 2

    `xy4: whiskerframe.coordinates.XYNamedTuple`
    :   Alias for field number 3

`RectangleCoordinates()`
:   Abstract coordinate interface for axis-aligned rectangular regions.
    
    Enable representation-agnostic conversion between the XYXY, XYWH, and
    four-vertex forms and compute anchor points for text and shape placement.
    Concrete subclasses implement :meth:`xyxy`, :meth:`xywh`, and :meth:`as_list`;
    the base class derives every other view (four vertices, width/height, anchor
    point) from the canonical bounding box returned by :meth:`xyxy`. This mirrors
    imagesmacker 7.0.0's ``RectangleCoordinates`` in strict parity.

    ### Descendants

    * whiskerframe.coordinates.FourXY
    * whiskerframe.coordinates.XYWH
    * whiskerframe.coordinates.XYXY

    ### Class variables

    `coordinates: <function NamedTuple at 0x7f0c465c6f20>`
    :   The type of the None singleton.

    `h: int`
    :   The type of the None singleton.

    `w: int`
    :   The type of the None singleton.

    ### Methods

    `anchor_coordinates(self, anchor: Anchor = 'mm') ‑> whiskerframe.coordinates.XY`
    :   Resolve a two-character anchor to its ``(x, y)`` pixel on the bounding box.
        
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

    `as_list(self) ‑> list[int] | list[typing.NamedTuple] | list[typing.Union[int, NamedTuple]]`
    :   Return the rectangle coordinates as a list.
        
        Returns:
        `list[int] | list[NamedTuple] | list[Union[int, NamedTuple]]`: The
        integer coordinates or vertex tuples of the representation.

    `as_tuple(self) ‑> tuple`
    :   Return the rectangle coordinates as a tuple.
        
        Returns:
        `tuple`: The tuple conversion of :meth:`as_list`.

    `fourxy(self) ‑> whiskerframe.coordinates.FourXYNamedTuple`
    :   Return the four corner vertices of the bounding box.
        
        Derive the vertices from the canonical bounding box in clockwise order
        starting from the top-left corner.
        
        Returns:
        `FourXYNamedTuple`: The four corner vertices, clockwise from top-left.

    `wh(self) ‑> whiskerframe.coordinates.WHNamedTuple`
    :   Return the rectangle dimensions as width and height.
        
        Returns:
        `WHNamedTuple`: The width and height of the rectangle.

    `xywh(self) ‑> whiskerframe.coordinates.XYWHNamedTuple`
    :   Return the bounding box in ``(x, y, w, h)`` form.
        
        Returns:
        `XYWHNamedTuple`: The top-left origin and the box dimensions.

    `xyxy(self) ‑> whiskerframe.coordinates.XYXYNamedTuple`
    :   Return the canonical bounding box in ``(x1, y1, x2, y2)`` form.
        
        Returns:
        `XYXYNamedTuple`: The top-left and bottom-right corner coordinates.

`WH(w: int, h: int)`
:   Two-dimensional dimensions with non-negative width and height.
    
    Initialize dimension metrics.
    
    Args:
    - w (`int`): Non-negative width value.
    - h (`int`): Non-negative height value.
    
    Raises:
    - `ValueError`: If either ``w`` or ``h`` is negative.
    
    Returns:
    `None`: This initializer does not return a value.

    ### Methods

    `wh(self) ‑> whiskerframe.coordinates.WHNamedTuple`
    :   Return the dimensions as a named tuple.
        
        Returns:
        `WHNamedTuple`: The ``(w, h)`` dimensions.

`WHNamedTuple(w: ForwardRef('int'), h: ForwardRef('int'))`
:   Two-dimensional size dimensions ``(w, h)``.

    ### Ancestors (in MRO)

    * builtins.tuple

    ### Instance variables

    `h: int`
    :   Alias for field number 1

    `w: int`
    :   Alias for field number 0

`XY(x: int, y: int)`
:   A two-dimensional point with non-negative integer coordinates.
    
    Initialize a 2D point coordinate.
    
    Args:
    - x (`int`): Non-negative horizontal coordinate.
    - y (`int`): Non-negative vertical coordinate.
    
    Raises:
    - `ValueError`: If either ``x`` or ``y`` is negative.
    
    Returns:
    `None`: This initializer does not return a value.

    ### Methods

    `xy(self) ‑> whiskerframe.coordinates.XYNamedTuple`
    :   Return the point coordinates as a named tuple.
        
        Returns:
        `XYNamedTuple`: The ``(x, y)`` coordinates.

`XYNamedTuple(x: ForwardRef('int'), y: ForwardRef('int'))`
:   Two-dimensional point coordinates ``(x, y)``.

    ### Ancestors (in MRO)

    * builtins.tuple

    ### Instance variables

    `x: int`
    :   Alias for field number 0

    `y: int`
    :   Alias for field number 1

`XYWH(x: int, y: int, w: int, h: int)`
:   An axis-aligned rectangle defined by an origin position and dimensions.
    
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

    ### Ancestors (in MRO)

    * whiskerframe.coordinates.RectangleCoordinates

    ### Methods

    `as_list(self) ‑> list[int]`
    :   Return the origin and dimensions as a four-integer list.
        
        Returns:
        `list[int]`: The list ``[x, y, w, h]``.

    `xywh(self) ‑> whiskerframe.coordinates.XYWHNamedTuple`
    :   Return the origin and dimensions as an ``XYWHNamedTuple``.
        
        Returns:
        `XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

    `xyxy(self) ‑> whiskerframe.coordinates.XYXYNamedTuple`
    :   Compute the opposing corner bounds as an ``XYXYNamedTuple``.
        
        Returns:
        `XYXYNamedTuple`: The ``(x, y, x + w, y + h)`` corner bounds.

`XYWHNamedTuple(x: ForwardRef('int'), y: ForwardRef('int'), w: ForwardRef('int'), h: ForwardRef('int'))`
:   Bounding box origin and dimensions ``(x, y, w, h)``.

    ### Ancestors (in MRO)

    * builtins.tuple

    ### Instance variables

    `h: int`
    :   Alias for field number 3

    `w: int`
    :   Alias for field number 2

    `x: int`
    :   Alias for field number 0

    `y: int`
    :   Alias for field number 1

`XYXY(x1: int, y1: int, x2: int, y2: int)`
:   An axis-aligned rectangle defined by two opposing corner coordinates.
    
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

    ### Ancestors (in MRO)

    * whiskerframe.coordinates.RectangleCoordinates

    ### Methods

    `as_list(self) ‑> list[int]`
    :   Return the corner bounds as a four-integer list.
        
        Returns:
        `list[int]`: The list ``[x1, y1, x2, y2]``.

    `xywh(self) ‑> whiskerframe.coordinates.XYWHNamedTuple`
    :   Return the origin and dimensions as an ``XYWHNamedTuple``.
        
        Returns:
        `XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

    `xyxy(self) ‑> whiskerframe.coordinates.XYXYNamedTuple`
    :   Return the corner bounds as an ``XYXYNamedTuple``.
        
        Returns:
        `XYXYNamedTuple`: The ``(x1, y1, x2, y2)`` corner bounds.

`XYXYNamedTuple(x1: ForwardRef('int'), y1: ForwardRef('int'), x2: ForwardRef('int'), y2: ForwardRef('int'))`
:   Bounding box corner coordinates ``(x1, y1, x2, y2)``.

    ### Ancestors (in MRO)

    * builtins.tuple

    ### Instance variables

    `x1: int`
    :   Alias for field number 0

    `x2: int`
    :   Alias for field number 2

    `y1: int`
    :   Alias for field number 1

    `y2: int`
    :   Alias for field number 3