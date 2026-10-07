<h1 id=""><a href="#">Module whiskerframe.coordinates</a></h1>

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

[← Go back to `whiskerframe`](./index.md)

<h2 id="variables"><a href="#variables">Variables</a></h2>

<h3 id="variables-coordinates_type_alias"><a href="#variables-coordinates_type_alias"><pre>coordinates_type_alias</pre></a></h3>

```python
TypeAlias
```

Discriminator for the simple coordinate types (``XY`` or ``WH``).

<h3 id="variables-rectangle_coordinates_type_alias"><a href="#variables-rectangle_coordinates_type_alias"><pre>rectangle_coordinates_type_alias</pre></a></h3>

```python
TypeAlias
```

Discriminator for the rectangle representations (``XYXY``/``XYWH``/``FourXY``).

<h2 id="functions"><a href="#functions">Functions</a></h2>

<h3 id="functions-distances_squared"><a href="#functions-distances_squared"><pre>distances_squared</pre></a></h3>

```python
(a: XYNamedTuple, b: XYNamedTuple) → int
```

Compute the squared Euclidean distance between two points.

Avoid a floating-point square root so distance comparisons stay exact.

Args:
- a (`XYNamedTuple`): First coordinate point.
- b (`XYNamedTuple`): Second coordinate point.

Returns:
`int`: The squared Euclidean distance between the points.

<h2 id="classes"><a href="#classes">Classes</a></h2>

<h3 id="classes-fourxy"><a href="#classes-fourxy"><pre>FourXY</pre></a></h3>

```python
(xy1: XYNamedTuple, xy2: XYNamedTuple, xy3: XYNamedTuple, xy4: XYNamedTuple)
```

A rectangle defined by four explicit corner vertices.

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

<h4 id="classes-fourxy-ancestors-in-mro"><a href="#classes-fourxy-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- whiskerframe.coordinates.RectangleCoordinates

<h4 id="classes-fourxy-class-variables"><a href="#classes-fourxy-class-variables">Class variables</a></h4>

<h5 id="classes-fourxy-class-variables-coordinates"><a href="#classes-fourxy-class-variables-coordinates"><pre>coordinates</pre></a></h5>

```python
<function NamedTuple at 0x7fc5018c2fc0>
```

The type of the None singleton.

<h5 id="classes-fourxy-class-variables-h"><a href="#classes-fourxy-class-variables-h"><pre>h</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-fourxy-class-variables-w"><a href="#classes-fourxy-class-variables-w"><pre>w</pre></a></h5>

```python
int
```

The type of the None singleton.

<h4 id="classes-fourxy-methods"><a href="#classes-fourxy-methods">Methods</a></h4>

<h5 id="classes-fourxy-methods-anchor_coordinates"><a href="#classes-fourxy-methods-anchor_coordinates"><pre>anchor_coordinates</pre></a></h5>

```python
(self, anchor: Anchor = 'mm') → whiskerframe.coordinates.XY
```

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

<h5 id="classes-fourxy-methods-as_list"><a href="#classes-fourxy-methods-as_list"><pre>as_list</pre></a></h5>

```python
(self) → list[typing.NamedTuple]
```

Return the corner points as a list of named tuples.

Returns:
`list[NamedTuple]`: The four corner coordinate points.

<h5 id="classes-fourxy-methods-as_tuple"><a href="#classes-fourxy-methods-as_tuple"><pre>as_tuple</pre></a></h5>

```python
(self) → tuple
```

Return the rectangle coordinates as a tuple.

Returns:
`tuple`: The tuple conversion of :meth:`as_list`.

<h5 id="classes-fourxy-methods-fourxy"><a href="#classes-fourxy-methods-fourxy"><pre>fourxy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.FourXYNamedTuple
```

Return the four corner points as a ``FourXYNamedTuple``.

Returns:
`FourXYNamedTuple`: The four corner vertices.

<h5 id="classes-fourxy-methods-wh"><a href="#classes-fourxy-methods-wh"><pre>wh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.WHNamedTuple
```

Return the rectangle dimensions as width and height.

Returns:
`WHNamedTuple`: The width and height of the rectangle.

<h5 id="classes-fourxy-methods-xywh"><a href="#classes-fourxy-methods-xywh"><pre>xywh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYWHNamedTuple
```

Return the axis-aligned bounding box origin and dimensions.

Returns:
`XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

<h5 id="classes-fourxy-methods-xyxy"><a href="#classes-fourxy-methods-xyxy"><pre>xyxy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYXYNamedTuple
```

Return the axis-aligned bounding box corner bounds.

Raises:
- `ValueError`: If the rectangle is not axis-aligned.

Returns:
`XYXYNamedTuple`: The minimum and maximum ``(x1, y1, x2, y2)`` bounds.

<h3 id="classes-fourxynamedtuple"><a href="#classes-fourxynamedtuple"><pre>FourXYNamedTuple</pre></a></h3>

```python
(xy1: ForwardRef('XYNamedTuple'), xy2: ForwardRef('XYNamedTuple'), xy3: ForwardRef('XYNamedTuple'), xy4: ForwardRef('XYNamedTuple'))
```

Four-vertex corner points defining a quadrilateral.

<h4 id="classes-fourxynamedtuple-ancestors-in-mro"><a href="#classes-fourxynamedtuple-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- builtins.tuple

<h4 id="classes-fourxynamedtuple-instance-variables"><a href="#classes-fourxynamedtuple-instance-variables">Instance variables</a></h4>

<h5 id="classes-fourxynamedtuple-instance-variables-xy1"><a href="#classes-fourxynamedtuple-instance-variables-xy1"><pre>xy1</pre></a></h5>

```python
whiskerframe.coordinates.XYNamedTuple
```

Alias for field number 0

<h5 id="classes-fourxynamedtuple-instance-variables-xy2"><a href="#classes-fourxynamedtuple-instance-variables-xy2"><pre>xy2</pre></a></h5>

```python
whiskerframe.coordinates.XYNamedTuple
```

Alias for field number 1

<h5 id="classes-fourxynamedtuple-instance-variables-xy3"><a href="#classes-fourxynamedtuple-instance-variables-xy3"><pre>xy3</pre></a></h5>

```python
whiskerframe.coordinates.XYNamedTuple
```

Alias for field number 2

<h5 id="classes-fourxynamedtuple-instance-variables-xy4"><a href="#classes-fourxynamedtuple-instance-variables-xy4"><pre>xy4</pre></a></h5>

```python
whiskerframe.coordinates.XYNamedTuple
```

Alias for field number 3

<h3 id="classes-rectanglecoordinates"><a href="#classes-rectanglecoordinates"><pre>RectangleCoordinates</pre></a></h3>

Abstract coordinate interface for axis-aligned rectangular regions.

Enable representation-agnostic conversion between the XYXY, XYWH, and
four-vertex forms and compute anchor points for text and shape placement.
Concrete subclasses implement :meth:`xyxy`, :meth:`xywh`, and :meth:`as_list`;
the base class derives every other view (four vertices, width/height, anchor
point) from the canonical bounding box returned by :meth:`xyxy`. This mirrors
imagesmacker 7.0.0's ``RectangleCoordinates`` in strict parity.

<h4 id="classes-rectanglecoordinates-descendants"><a href="#classes-rectanglecoordinates-descendants">Descendants</a></h4>

- whiskerframe.coordinates.FourXY
- whiskerframe.coordinates.XYWH
- whiskerframe.coordinates.XYXY

<h4 id="classes-rectanglecoordinates-class-variables"><a href="#classes-rectanglecoordinates-class-variables">Class variables</a></h4>

<h5 id="classes-rectanglecoordinates-class-variables-coordinates"><a href="#classes-rectanglecoordinates-class-variables-coordinates"><pre>coordinates</pre></a></h5>

```python
<function NamedTuple at 0x7fc5018c2fc0>
```

The type of the None singleton.

<h5 id="classes-rectanglecoordinates-class-variables-h"><a href="#classes-rectanglecoordinates-class-variables-h"><pre>h</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-rectanglecoordinates-class-variables-w"><a href="#classes-rectanglecoordinates-class-variables-w"><pre>w</pre></a></h5>

```python
int
```

The type of the None singleton.

<h4 id="classes-rectanglecoordinates-methods"><a href="#classes-rectanglecoordinates-methods">Methods</a></h4>

<h5 id="classes-rectanglecoordinates-methods-anchor_coordinates"><a href="#classes-rectanglecoordinates-methods-anchor_coordinates"><pre>anchor_coordinates</pre></a></h5>

```python
(self, anchor: Anchor = 'mm') → whiskerframe.coordinates.XY
```

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

<h5 id="classes-rectanglecoordinates-methods-as_list"><a href="#classes-rectanglecoordinates-methods-as_list"><pre>as_list</pre></a></h5>

```python
(self) → list[int] | list[typing.NamedTuple] | list[typing.Union[int, NamedTuple]]
```

Return the rectangle coordinates as a list.

Returns:
`list[int] | list[NamedTuple] | list[Union[int, NamedTuple]]`: The
integer coordinates or vertex tuples of the representation.

<h5 id="classes-rectanglecoordinates-methods-as_tuple"><a href="#classes-rectanglecoordinates-methods-as_tuple"><pre>as_tuple</pre></a></h5>

```python
(self) → tuple
```

Return the rectangle coordinates as a tuple.

Returns:
`tuple`: The tuple conversion of :meth:`as_list`.

<h5 id="classes-rectanglecoordinates-methods-fourxy"><a href="#classes-rectanglecoordinates-methods-fourxy"><pre>fourxy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.FourXYNamedTuple
```

Return the four corner vertices of the bounding box.

Derive the vertices from the canonical bounding box in clockwise order
starting from the top-left corner.

Returns:
`FourXYNamedTuple`: The four corner vertices, clockwise from top-left.

<h5 id="classes-rectanglecoordinates-methods-wh"><a href="#classes-rectanglecoordinates-methods-wh"><pre>wh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.WHNamedTuple
```

Return the rectangle dimensions as width and height.

Returns:
`WHNamedTuple`: The width and height of the rectangle.

<h5 id="classes-rectanglecoordinates-methods-xywh"><a href="#classes-rectanglecoordinates-methods-xywh"><pre>xywh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYWHNamedTuple
```

Return the bounding box in ``(x, y, w, h)`` form.

Returns:
`XYWHNamedTuple`: The top-left origin and the box dimensions.

<h5 id="classes-rectanglecoordinates-methods-xyxy"><a href="#classes-rectanglecoordinates-methods-xyxy"><pre>xyxy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYXYNamedTuple
```

Return the canonical bounding box in ``(x1, y1, x2, y2)`` form.

Returns:
`XYXYNamedTuple`: The top-left and bottom-right corner coordinates.

<h3 id="classes-wh"><a href="#classes-wh"><pre>WH</pre></a></h3>

```python
(w: int, h: int)
```

Two-dimensional dimensions with non-negative width and height.

Initialize dimension metrics.

Args:
- w (`int`): Non-negative width value.
- h (`int`): Non-negative height value.

Raises:
- `ValueError`: If either ``w`` or ``h`` is negative.

Returns:
`None`: This initializer does not return a value.

<h4 id="classes-wh-methods"><a href="#classes-wh-methods">Methods</a></h4>

<h5 id="classes-wh-methods-wh"><a href="#classes-wh-methods-wh"><pre>wh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.WHNamedTuple
```

Return the dimensions as a named tuple.

Returns:
`WHNamedTuple`: The ``(w, h)`` dimensions.

<h3 id="classes-whnamedtuple"><a href="#classes-whnamedtuple"><pre>WHNamedTuple</pre></a></h3>

```python
(w: ForwardRef('int'), h: ForwardRef('int'))
```

Two-dimensional size dimensions ``(w, h)``.

<h4 id="classes-whnamedtuple-ancestors-in-mro"><a href="#classes-whnamedtuple-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- builtins.tuple

<h4 id="classes-whnamedtuple-instance-variables"><a href="#classes-whnamedtuple-instance-variables">Instance variables</a></h4>

<h5 id="classes-whnamedtuple-instance-variables-h"><a href="#classes-whnamedtuple-instance-variables-h"><pre>h</pre></a></h5>

```python
int
```

Alias for field number 1

<h5 id="classes-whnamedtuple-instance-variables-w"><a href="#classes-whnamedtuple-instance-variables-w"><pre>w</pre></a></h5>

```python
int
```

Alias for field number 0

<h3 id="classes-xy"><a href="#classes-xy"><pre>XY</pre></a></h3>

```python
(x: int, y: int)
```

A two-dimensional point with non-negative integer coordinates.

Initialize a 2D point coordinate.

Args:
- x (`int`): Non-negative horizontal coordinate.
- y (`int`): Non-negative vertical coordinate.

Raises:
- `ValueError`: If either ``x`` or ``y`` is negative.

Returns:
`None`: This initializer does not return a value.

<h4 id="classes-xy-methods"><a href="#classes-xy-methods">Methods</a></h4>

<h5 id="classes-xy-methods-xy"><a href="#classes-xy-methods-xy"><pre>xy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYNamedTuple
```

Return the point coordinates as a named tuple.

Returns:
`XYNamedTuple`: The ``(x, y)`` coordinates.

<h3 id="classes-xynamedtuple"><a href="#classes-xynamedtuple"><pre>XYNamedTuple</pre></a></h3>

```python
(x: ForwardRef('int'), y: ForwardRef('int'))
```

Two-dimensional point coordinates ``(x, y)``.

<h4 id="classes-xynamedtuple-ancestors-in-mro"><a href="#classes-xynamedtuple-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- builtins.tuple

<h4 id="classes-xynamedtuple-instance-variables"><a href="#classes-xynamedtuple-instance-variables">Instance variables</a></h4>

<h5 id="classes-xynamedtuple-instance-variables-x"><a href="#classes-xynamedtuple-instance-variables-x"><pre>x</pre></a></h5>

```python
int
```

Alias for field number 0

<h5 id="classes-xynamedtuple-instance-variables-y"><a href="#classes-xynamedtuple-instance-variables-y"><pre>y</pre></a></h5>

```python
int
```

Alias for field number 1

<h3 id="classes-xywh"><a href="#classes-xywh"><pre>XYWH</pre></a></h3>

```python
(x: int, y: int, w: int, h: int)
```

An axis-aligned rectangle defined by an origin position and dimensions.

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

<h4 id="classes-xywh-ancestors-in-mro"><a href="#classes-xywh-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- whiskerframe.coordinates.RectangleCoordinates

<h4 id="classes-xywh-class-variables"><a href="#classes-xywh-class-variables">Class variables</a></h4>

<h5 id="classes-xywh-class-variables-coordinates"><a href="#classes-xywh-class-variables-coordinates"><pre>coordinates</pre></a></h5>

```python
<function NamedTuple at 0x7fc5018c2fc0>
```

The type of the None singleton.

<h5 id="classes-xywh-class-variables-h"><a href="#classes-xywh-class-variables-h"><pre>h</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-xywh-class-variables-w"><a href="#classes-xywh-class-variables-w"><pre>w</pre></a></h5>

```python
int
```

The type of the None singleton.

<h4 id="classes-xywh-methods"><a href="#classes-xywh-methods">Methods</a></h4>

<h5 id="classes-xywh-methods-anchor_coordinates"><a href="#classes-xywh-methods-anchor_coordinates"><pre>anchor_coordinates</pre></a></h5>

```python
(self, anchor: Anchor = 'mm') → whiskerframe.coordinates.XY
```

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

<h5 id="classes-xywh-methods-as_list"><a href="#classes-xywh-methods-as_list"><pre>as_list</pre></a></h5>

```python
(self) → list[int]
```

Return the origin and dimensions as a four-integer list.

Returns:
`list[int]`: The list ``[x, y, w, h]``.

<h5 id="classes-xywh-methods-as_tuple"><a href="#classes-xywh-methods-as_tuple"><pre>as_tuple</pre></a></h5>

```python
(self) → tuple
```

Return the rectangle coordinates as a tuple.

Returns:
`tuple`: The tuple conversion of :meth:`as_list`.

<h5 id="classes-xywh-methods-fourxy"><a href="#classes-xywh-methods-fourxy"><pre>fourxy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.FourXYNamedTuple
```

Return the four corner vertices of the bounding box.

Derive the vertices from the canonical bounding box in clockwise order
starting from the top-left corner.

Returns:
`FourXYNamedTuple`: The four corner vertices, clockwise from top-left.

<h5 id="classes-xywh-methods-wh"><a href="#classes-xywh-methods-wh"><pre>wh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.WHNamedTuple
```

Return the rectangle dimensions as width and height.

Returns:
`WHNamedTuple`: The width and height of the rectangle.

<h5 id="classes-xywh-methods-xywh"><a href="#classes-xywh-methods-xywh"><pre>xywh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYWHNamedTuple
```

Return the origin and dimensions as an ``XYWHNamedTuple``.

Returns:
`XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

<h5 id="classes-xywh-methods-xyxy"><a href="#classes-xywh-methods-xyxy"><pre>xyxy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYXYNamedTuple
```

Compute the opposing corner bounds as an ``XYXYNamedTuple``.

Returns:
`XYXYNamedTuple`: The ``(x, y, x + w, y + h)`` corner bounds.

<h3 id="classes-xywhnamedtuple"><a href="#classes-xywhnamedtuple"><pre>XYWHNamedTuple</pre></a></h3>

```python
(x: ForwardRef('int'), y: ForwardRef('int'), w: ForwardRef('int'), h: ForwardRef('int'))
```

Bounding box origin and dimensions ``(x, y, w, h)``.

<h4 id="classes-xywhnamedtuple-ancestors-in-mro"><a href="#classes-xywhnamedtuple-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- builtins.tuple

<h4 id="classes-xywhnamedtuple-instance-variables"><a href="#classes-xywhnamedtuple-instance-variables">Instance variables</a></h4>

<h5 id="classes-xywhnamedtuple-instance-variables-h"><a href="#classes-xywhnamedtuple-instance-variables-h"><pre>h</pre></a></h5>

```python
int
```

Alias for field number 3

<h5 id="classes-xywhnamedtuple-instance-variables-w"><a href="#classes-xywhnamedtuple-instance-variables-w"><pre>w</pre></a></h5>

```python
int
```

Alias for field number 2

<h5 id="classes-xywhnamedtuple-instance-variables-x"><a href="#classes-xywhnamedtuple-instance-variables-x"><pre>x</pre></a></h5>

```python
int
```

Alias for field number 0

<h5 id="classes-xywhnamedtuple-instance-variables-y"><a href="#classes-xywhnamedtuple-instance-variables-y"><pre>y</pre></a></h5>

```python
int
```

Alias for field number 1

<h3 id="classes-xyxy"><a href="#classes-xyxy"><pre>XYXY</pre></a></h3>

```python
(x1: int, y1: int, x2: int, y2: int)
```

An axis-aligned rectangle defined by two opposing corner coordinates.

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

<h4 id="classes-xyxy-ancestors-in-mro"><a href="#classes-xyxy-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- whiskerframe.coordinates.RectangleCoordinates

<h4 id="classes-xyxy-class-variables"><a href="#classes-xyxy-class-variables">Class variables</a></h4>

<h5 id="classes-xyxy-class-variables-coordinates"><a href="#classes-xyxy-class-variables-coordinates"><pre>coordinates</pre></a></h5>

```python
<function NamedTuple at 0x7fc5018c2fc0>
```

The type of the None singleton.

<h5 id="classes-xyxy-class-variables-h"><a href="#classes-xyxy-class-variables-h"><pre>h</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-xyxy-class-variables-w"><a href="#classes-xyxy-class-variables-w"><pre>w</pre></a></h5>

```python
int
```

The type of the None singleton.

<h4 id="classes-xyxy-methods"><a href="#classes-xyxy-methods">Methods</a></h4>

<h5 id="classes-xyxy-methods-anchor_coordinates"><a href="#classes-xyxy-methods-anchor_coordinates"><pre>anchor_coordinates</pre></a></h5>

```python
(self, anchor: Anchor = 'mm') → whiskerframe.coordinates.XY
```

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

<h5 id="classes-xyxy-methods-as_list"><a href="#classes-xyxy-methods-as_list"><pre>as_list</pre></a></h5>

```python
(self) → list[int]
```

Return the corner bounds as a four-integer list.

Returns:
`list[int]`: The list ``[x1, y1, x2, y2]``.

<h5 id="classes-xyxy-methods-as_tuple"><a href="#classes-xyxy-methods-as_tuple"><pre>as_tuple</pre></a></h5>

```python
(self) → tuple
```

Return the rectangle coordinates as a tuple.

Returns:
`tuple`: The tuple conversion of :meth:`as_list`.

<h5 id="classes-xyxy-methods-fourxy"><a href="#classes-xyxy-methods-fourxy"><pre>fourxy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.FourXYNamedTuple
```

Return the four corner vertices of the bounding box.

Derive the vertices from the canonical bounding box in clockwise order
starting from the top-left corner.

Returns:
`FourXYNamedTuple`: The four corner vertices, clockwise from top-left.

<h5 id="classes-xyxy-methods-wh"><a href="#classes-xyxy-methods-wh"><pre>wh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.WHNamedTuple
```

Return the rectangle dimensions as width and height.

Returns:
`WHNamedTuple`: The width and height of the rectangle.

<h5 id="classes-xyxy-methods-xywh"><a href="#classes-xyxy-methods-xywh"><pre>xywh</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYWHNamedTuple
```

Return the origin and dimensions as an ``XYWHNamedTuple``.

Returns:
`XYWHNamedTuple`: The ``(x, y, w, h)`` origin and dimensions.

<h5 id="classes-xyxy-methods-xyxy"><a href="#classes-xyxy-methods-xyxy"><pre>xyxy</pre></a></h5>

```python
(self) → whiskerframe.coordinates.XYXYNamedTuple
```

Return the corner bounds as an ``XYXYNamedTuple``.

Returns:
`XYXYNamedTuple`: The ``(x1, y1, x2, y2)`` corner bounds.

<h3 id="classes-xyxynamedtuple"><a href="#classes-xyxynamedtuple"><pre>XYXYNamedTuple</pre></a></h3>

```python
(x1: ForwardRef('int'), y1: ForwardRef('int'), x2: ForwardRef('int'), y2: ForwardRef('int'))
```

Bounding box corner coordinates ``(x1, y1, x2, y2)``.

<h4 id="classes-xyxynamedtuple-ancestors-in-mro"><a href="#classes-xyxynamedtuple-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- builtins.tuple

<h4 id="classes-xyxynamedtuple-instance-variables"><a href="#classes-xyxynamedtuple-instance-variables">Instance variables</a></h4>

<h5 id="classes-xyxynamedtuple-instance-variables-x1"><a href="#classes-xyxynamedtuple-instance-variables-x1"><pre>x1</pre></a></h5>

```python
int
```

Alias for field number 0

<h5 id="classes-xyxynamedtuple-instance-variables-x2"><a href="#classes-xyxynamedtuple-instance-variables-x2"><pre>x2</pre></a></h5>

```python
int
```

Alias for field number 2

<h5 id="classes-xyxynamedtuple-instance-variables-y1"><a href="#classes-xyxynamedtuple-instance-variables-y1"><pre>y1</pre></a></h5>

```python
int
```

Alias for field number 1

<h5 id="classes-xyxynamedtuple-instance-variables-y2"><a href="#classes-xyxynamedtuple-instance-variables-y2"><pre>y2</pre></a></h5>

```python
int
```

Alias for field number 3

---

[← Go back to `whiskerframe`](./index.md)