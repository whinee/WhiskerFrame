<h1 id=""><a href="#">Module whiskerframe.metrics</a></h1>

Static font-metrics table and pure text-sizing helpers (no Pillow).

Multiline text layout in the command path needs glyph metrics to measure line
widths and stack lines by height. Shipping a static width/height table lets the
`Command_Builder` size text without importing Pillow, keeping the serial command
path free of an imaging dependency (Req 3.2). The optional `Preview_Renderer`
reuses these same helpers so preview placement matches device placement.

The metrics model a fixed-cell font: for a given ``font_size`` selector every
glyph occupies a cell of ``cell_width`` x ``cell_height`` pixels, and a line
advances vertically by ``line_advance`` pixels. This matches the TFT_eSPI
built-in fonts used by the firmware, whose glyphs share a common cell.

[← Go back to `whiskerframe`](./index.md)

<h2 id="variables"><a href="#variables">Variables</a></h2>

<h3 id="variables-default_font_size"><a href="#variables-default_font_size"><pre>DEFAULT_FONT_SIZE</pre></a></h3>

```python
int
```

Default ``font_size`` selector used when a caller omits one.

<h3 id="variables-font_metrics"><a href="#variables-font_metrics"><pre>FONT_METRICS</pre></a></h3>

```python
dict[int, whiskerframe.metrics.FontMetrics]
```

Static per-``font_size`` metrics table (pure data, no Pillow).

Keys are the ``font_size`` selectors carried in the ``DRAW_TEXT`` payload; each
value is the fixed-cell `FontMetrics` for that size. Sizes scale the base
6x8 cell linearly, matching TFT_eSPI text-size multipliers.

<h2 id="functions"><a href="#functions">Functions</a></h2>

<h3 id="functions-line_advance"><a href="#functions-line_advance"><pre>line_advance</pre></a></h3>

```python
(font_size: int = 1) → int
```

Return the default vertical advance between successive line origins.

This is the fallback ``line_height`` used for multiline stacking when the
caller does not supply an explicit value.

Args:
- font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.

Raises:
- `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

Returns:
`int`: Vertical distance between line origins in pixels.

<h3 id="functions-line_height"><a href="#functions-line_height"><pre>line_height</pre></a></h3>

```python
(font_size: int = 1) → int
```

Return the pixel height of one glyph cell.

Args:
- font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.

Raises:
- `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

Returns:
`int`: Height of one line's glyph cell in pixels.

<h3 id="functions-line_width"><a href="#functions-line_width"><pre>line_width</pre></a></h3>

```python
(line: str, font_size: int = 1) → int
```

Measure the pixel width of a single line of text.

The line is treated as fixed-cell, so its width is the glyph count times the
cell advance width. Any newline characters are ignored; callers should split
multiline text before measuring individual lines.

Args:
- line (`str`): Single line of text to measure.
- font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.

Raises:
- `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

Returns:
`int`: Width of the line in pixels.

<h3 id="functions-text_height"><a href="#functions-text_height"><pre>text_height</pre></a></h3>

```python
(text: str, font_size: int = 1, line_height_px: int | None = None) → int
```

Measure the stacked pixel height of a (possibly multiline) text block.

Lines are split on ``\\n`` and stacked so that each line origin is advanced
by ``line_height_px``. The total height is ``(n - 1) * advance + cell_height``
for ``n`` lines, matching the multiline stacking the `Command_Builder` uses.

Args:
- text (`str`): Text block, with lines separated by ``\\n``.
- font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.
- line_height_px (`int`, optional): Per-line vertical advance. Defaults to the font's `line_advance`.

Raises:
- `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

Returns:
`int`: Total stacked height in pixels.

<h3 id="functions-text_size"><a href="#functions-text_size"><pre>text_size</pre></a></h3>

```python
(text: str, font_size: int = 1, line_height_px: int | None = None) → whiskerframe.metrics.TextSize
```

Measure the pixel dimensions of a (possibly multiline) text block.

Combines `text_width` and `text_height` into a single `TextSize`, giving the
`Command_Builder` the block extent it needs to resolve a block anchor origin.

Args:
- text (`str`): Text block, with lines separated by ``\\n``.
- font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.
- line_height_px (`int`, optional): Per-line vertical advance. Defaults to the font's `line_advance`.

Raises:
- `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

Returns:
`TextSize`: Width and stacked height of the text block in pixels.

<h3 id="functions-text_width"><a href="#functions-text_width"><pre>text_width</pre></a></h3>

```python
(text: str, font_size: int = 1) → int
```

Measure the pixel width of a (possibly multiline) text block.

The block width is the width of its widest line. Lines are split on ``\\n``.

Args:
- text (`str`): Text block, with lines separated by ``\\n``.
- font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.

Raises:
- `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

Returns:
`int`: Width of the widest line in pixels.

<h2 id="classes"><a href="#classes">Classes</a></h2>

<h3 id="classes-fontmetrics"><a href="#classes-fontmetrics"><pre>FontMetrics</pre></a></h3>

```python
(cell_width: ForwardRef('int'), cell_height: ForwardRef('int'), line_advance: ForwardRef('int'))
```

Fixed-cell glyph metrics for a single ``font_size`` selector.

Every glyph in the font is treated as occupying a uniform cell, matching the
TFT_eSPI built-in bitmap fonts. Line stacking advances by ``line_advance``,
which may exceed ``cell_height`` to provide inter-line leading.

Attributes:
- cell_width (`int`): Advance width of one glyph cell, in pixels.
- cell_height (`int`): Height of one glyph cell, in pixels.
- line_advance (`int`): Vertical distance between successive line origins, in pixels.

<h4 id="classes-fontmetrics-ancestors-in-mro"><a href="#classes-fontmetrics-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- builtins.tuple

<h4 id="classes-fontmetrics-instance-variables"><a href="#classes-fontmetrics-instance-variables">Instance variables</a></h4>

<h5 id="classes-fontmetrics-instance-variables-cell_height"><a href="#classes-fontmetrics-instance-variables-cell_height"><pre>cell_height</pre></a></h5>

```python
int
```

Alias for field number 1

<h5 id="classes-fontmetrics-instance-variables-cell_width"><a href="#classes-fontmetrics-instance-variables-cell_width"><pre>cell_width</pre></a></h5>

```python
int
```

Alias for field number 0

<h5 id="classes-fontmetrics-instance-variables-line_advance"><a href="#classes-fontmetrics-instance-variables-line_advance"><pre>line_advance</pre></a></h5>

```python
int
```

Alias for field number 2

<h3 id="classes-textsize"><a href="#classes-textsize"><pre>TextSize</pre></a></h3>

```python
(width: ForwardRef('int'), height: ForwardRef('int'))
```

Pixel dimensions of a rendered text block.

Attributes:
- width (`int`): Width of the widest line, in pixels.
- height (`int`): Total stacked height of all lines, in pixels.

<h4 id="classes-textsize-ancestors-in-mro"><a href="#classes-textsize-ancestors-in-mro">Ancestors (in MRO)</a></h4>

- builtins.tuple

<h4 id="classes-textsize-instance-variables"><a href="#classes-textsize-instance-variables">Instance variables</a></h4>

<h5 id="classes-textsize-instance-variables-height"><a href="#classes-textsize-instance-variables-height"><pre>height</pre></a></h5>

```python
int
```

Alias for field number 1

<h5 id="classes-textsize-instance-variables-width"><a href="#classes-textsize-instance-variables-width"><pre>width</pre></a></h5>

```python
int
```

Alias for field number 0

---

[← Go back to `whiskerframe`](./index.md)