<h1 id=""><a href="#">Module whiskerframe.terminal</a></h1>

Terminal grid geometry and the new terminal wire-command models.

Extend the CYD Display Link command path with the host-side pieces the
``cyd-terminal`` feature needs: a pure :class:`TerminalGeometry` that derives the
character-grid dimensions for the fixed 320x240 panel from a ``font_size``
selector (reusing :data:`whiskerframe.metrics.FONT_METRICS`), and three validated
pydantic command models matching the new wire payloads: :class:`DrawCells` (a run
of fixed-cell glyphs on one text row), :class:`Scroll` (shift a row band up or
down), and :class:`DrawImage` (a rectangular block of raw RGB565 pixels, used for
the boot splash).

Field ranges mirror the wire encoding: cell/pixel coordinates and colors are
``uint16`` (0-65535), ``font_size`` is ``uint8`` (0-255), and
:attr:`Scroll.rows` is a *signed* ``int8`` (-128..127, positive scrolls up). The
models validate at construction (pydantic v2), so an out-of-range value is
rejected before it can reach the serializer.

This module is pure: it imports no Pillow (or any imaging library) and no
hardware driver, so it stays usable on the serial command path and in host tests.

[← Go back to `whiskerframe`](./index.md)

<h2 id="variables"><a href="#variables">Variables</a></h2>

<h3 id="variables-display_height"><a href="#variables-display_height"><pre>DISPLAY_HEIGHT</pre></a></h3>

```python
int
```

Visible panel height in pixels (landscape, TFT_eSPI rotation 1).

<h3 id="variables-display_width"><a href="#variables-display_width"><pre>DISPLAY_WIDTH</pre></a></h3>

```python
int
```

Visible panel width in pixels (landscape, TFT_eSPI rotation 1).

<h3 id="variables-int8_max"><a href="#variables-int8_max"><pre>INT8_MAX</pre></a></h3>

```python
int
```

Maximum value of a signed ``int8`` wire field.

<h3 id="variables-int8_min"><a href="#variables-int8_min"><pre>INT8_MIN</pre></a></h3>

```python
int
```

Minimum value of a signed ``int8`` wire field.

<h2 id="classes"><a href="#classes">Classes</a></h2>

<h3 id="classes-drawcells"><a href="#classes-drawcells"><pre>DrawCells</pre></a></h3>

```python
(**data: Any)
```

Resolved ``DRAW_CELLS`` (``0x03``) command: a run of glyphs on one text row.

Hold the fields the serializer encodes into a ``DRAW_CELLS`` payload: the
starting cell ``(col, row)`` (both ``uint16``), the RGB565 ``fg``/``bg``
colors (``uint16``), the ``uint8`` ``font_size`` selector, and the run
``text``. Each character occupies one fixed-cell position, so ``text`` is
encoded one byte per cell (CP437/latin-1-safe) and bounded to ``uint16``
length.

The model is validated on construction (pydantic v2): coordinates and colors
are bounded to ``uint16``, ``font_size`` to ``uint8``, and ``text`` to at most
65535 characters, so an out-of-range value is rejected before the wire.

Attributes:
- col (`int`): Starting column in cell units, in ``[0, 65535]``.
- row (`int`): Starting row in cell units, in ``[0, 65535]``.
- fg (`int`): RGB565 foreground color in ``[0, 65535]``.
- bg (`int`): RGB565 background color in ``[0, 65535]``.
- font_size (`int`): ``uint8`` font-size selector in ``[0, 255]``.
- text (`str`): Run text, one character per cell (<= 65535 chars).

Create a new model by parsing and validating input data from keyword arguments.

Raises [`ValidationError`][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

`self` is explicitly positional-only to allow `self` as a field name.

<h4 id="classes-drawcells-ancestors-in-mro"><a href="#classes-drawcells-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- pydantic.main.BaseModel

<h4 id="classes-drawcells-class-variables"><a href="#classes-drawcells-class-variables">Class variables</a></h4>

<h5 id="classes-drawcells-class-variables-bg"><a href="#classes-drawcells-class-variables-bg"><pre>bg</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-drawcells-class-variables-col"><a href="#classes-drawcells-class-variables-col"><pre>col</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-drawcells-class-variables-fg"><a href="#classes-drawcells-class-variables-fg"><pre>fg</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-drawcells-class-variables-font_size"><a href="#classes-drawcells-class-variables-font_size"><pre>font_size</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-drawcells-class-variables-model_config"><a href="#classes-drawcells-class-variables-model_config"><pre>model_config</pre></a></h5>

The type of the None singleton.

<h5 id="classes-drawcells-class-variables-row"><a href="#classes-drawcells-class-variables-row"><pre>row</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-drawcells-class-variables-text"><a href="#classes-drawcells-class-variables-text"><pre>text</pre></a></h5>

```python
str
```

The type of the None singleton.

<h3 id="classes-drawimage"><a href="#classes-drawimage"><pre>DrawImage</pre></a></h3>

```python
(**data: Any)
```

Resolved ``DRAW_IMAGE`` (``0x05``) command: a block of raw RGB565 pixels.

Hold the fields the serializer encodes into a ``DRAW_IMAGE`` payload: the
top-left pixel ``(x, y)`` and the block dimensions ``(w, h)`` (all ``uint16``),
followed by ``data``, the raw RGB565 pixel bytes for the ``w * h`` block. Each
pixel is two bytes, so ``len(data)`` MUST equal ``w * h * 2``. A full splash
image is sent as a sequence of these blocks (chunked rows).

The model is validated on construction (pydantic v2): coordinates and
dimensions are bounded to ``uint16`` and ``data`` length is cross-checked
against ``w * h * 2``.

Attributes:
- x (`int`): Top-left x pixel in ``[0, 65535]``.
- y (`int`): Top-left y pixel in ``[0, 65535]``.
- w (`int`): Block width in pixels, in ``[0, 65535]``.
- h (`int`): Block height in pixels, in ``[0, 65535]``.
- data (`bytes`): Raw RGB565 pixel bytes; length MUST equal ``w * h * 2``.

Create a new model by parsing and validating input data from keyword arguments.

Raises [`ValidationError`][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

`self` is explicitly positional-only to allow `self` as a field name.

<h4 id="classes-drawimage-ancestors-in-mro"><a href="#classes-drawimage-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- pydantic.main.BaseModel

<h4 id="classes-drawimage-class-variables"><a href="#classes-drawimage-class-variables">Class variables</a></h4>

<h5 id="classes-drawimage-class-variables-data"><a href="#classes-drawimage-class-variables-data"><pre>data</pre></a></h5>

```python
bytes
```

The type of the None singleton.

<h5 id="classes-drawimage-class-variables-h"><a href="#classes-drawimage-class-variables-h"><pre>h</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-drawimage-class-variables-model_config"><a href="#classes-drawimage-class-variables-model_config"><pre>model_config</pre></a></h5>

The type of the None singleton.

<h5 id="classes-drawimage-class-variables-w"><a href="#classes-drawimage-class-variables-w"><pre>w</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-drawimage-class-variables-x"><a href="#classes-drawimage-class-variables-x"><pre>x</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-drawimage-class-variables-y"><a href="#classes-drawimage-class-variables-y"><pre>y</pre></a></h5>

```python
int
```

The type of the None singleton.

<h3 id="classes-scroll"><a href="#classes-scroll"><pre>Scroll</pre></a></h3>

```python
(**data: Any)
```

Resolved ``SCROLL`` (``0x04``) command: shift a row band up or down.

Hold the fields the serializer encodes into a ``SCROLL`` payload: a *signed*
``int8`` ``rows`` count (positive scrolls the band up, negative down), the
RGB565 ``fill`` color for the vacated rows (``uint16``), and the inclusive
``top``/``bottom`` row bounds of the scroll region in cell units (``uint16``).

The model is validated on construction (pydantic v2): ``rows`` is bounded to
the signed ``int8`` range (-128..127), ``fill`` to ``uint16``, and the row
bounds to ``uint16``.

Attributes:
- rows (`int`): Signed row shift in ``[-128, 127]`` (+ up, - down).
- fill (`int`): RGB565 color for the vacated rows in ``[0, 65535]``.
- top (`int`): First row of the scroll region (cell units) in ``[0, 65535]``.
- bottom (`int`): Last row of the scroll region (cell units) in ``[0, 65535]``.

Create a new model by parsing and validating input data from keyword arguments.

Raises [`ValidationError`][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

`self` is explicitly positional-only to allow `self` as a field name.

<h4 id="classes-scroll-ancestors-in-mro"><a href="#classes-scroll-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- pydantic.main.BaseModel

<h4 id="classes-scroll-class-variables"><a href="#classes-scroll-class-variables">Class variables</a></h4>

<h5 id="classes-scroll-class-variables-bottom"><a href="#classes-scroll-class-variables-bottom"><pre>bottom</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-scroll-class-variables-fill"><a href="#classes-scroll-class-variables-fill"><pre>fill</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-scroll-class-variables-model_config"><a href="#classes-scroll-class-variables-model_config"><pre>model_config</pre></a></h5>

The type of the None singleton.

<h5 id="classes-scroll-class-variables-rows"><a href="#classes-scroll-class-variables-rows"><pre>rows</pre></a></h5>

```python
int
```

The type of the None singleton.

<h5 id="classes-scroll-class-variables-top"><a href="#classes-scroll-class-variables-top"><pre>top</pre></a></h5>

```python
int
```

The type of the None singleton.

<h3 id="classes-terminalgeometry"><a href="#classes-terminalgeometry"><pre>TerminalGeometry</pre></a></h3>

```python
(cols: ForwardRef('int'), rows: ForwardRef('int'), cell_w: ForwardRef('int'), cell_h: ForwardRef('int'))
```

Character-grid geometry for the 320x240 panel at a given ``font_size``.

Derive the terminal's column/row counts and per-cell pixel dimensions from a
``font_size`` selector and the fixed `whiskerframe.metrics.FONT_METRICS`
cell sizes, flooring the panel extent by the cell extent so the grid never
overflows the visible area. For the shipped sizes this yields size 1 ->
53x30, size 2 -> 26x15, size 3 -> 17x10.

Construct instances via :meth:`for_font_size` rather than directly, so the
geometry always matches the metrics table.

Attributes:
- cols (`int`): Number of character columns that fit horizontally.
- rows (`int`): Number of character rows that fit vertically.
- cell_w (`int`): Width of one cell in pixels.
- cell_h (`int`): Height of one cell in pixels.

<h4 id="classes-terminalgeometry-ancestors-in-mro"><a href="#classes-terminalgeometry-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- builtins.tuple

<h4 id="classes-terminalgeometry-static-methods"><a href="#classes-terminalgeometry-static-methods">Static methods</a></h4>

<h5 id="classes-terminalgeometry-static-methods-for_font_size"><a href="#classes-terminalgeometry-static-methods-for_font_size"><pre>for_font_size</pre></a></h5>

```python
(font_size: int) → whiskerframe.terminal.TerminalGeometry
```

Compute the grid geometry for a ``font_size`` selector.

Look up the fixed-cell metrics for ``font_size`` and floor-divide the
320x240 panel by the cell width/height to get the column and row counts.

Args:
- font_size (`int`): Font-size selector indexing `FONT_METRICS`.

Raises:
- `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

Returns:
`TerminalGeometry`: The grid dimensions and cell size for the font.

<h4 id="classes-terminalgeometry-instance-variables"><a href="#classes-terminalgeometry-instance-variables">Instance variables</a></h4>

<h5 id="classes-terminalgeometry-instance-variables-cell_h"><a href="#classes-terminalgeometry-instance-variables-cell_h"><pre>cell_h</pre></a></h5>

```python
int
```

Alias for field number 3

<h5 id="classes-terminalgeometry-instance-variables-cell_w"><a href="#classes-terminalgeometry-instance-variables-cell_w"><pre>cell_w</pre></a></h5>

```python
int
```

Alias for field number 2

<h5 id="classes-terminalgeometry-instance-variables-cols"><a href="#classes-terminalgeometry-instance-variables-cols"><pre>cols</pre></a></h5>

```python
int
```

Alias for field number 0

<h5 id="classes-terminalgeometry-instance-variables-rows"><a href="#classes-terminalgeometry-instance-variables-rows"><pre>rows</pre></a></h5>

```python
int
```

Alias for field number 1

---

[← Go back to `whiskerframe`](./index.md)