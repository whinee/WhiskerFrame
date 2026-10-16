<h1 id=""><a href="#">Module whiskerframe.preview</a></h1>

Optional Pillow-based host-side preview renderer for the CYD Display Link.

Render a host-side image of resolved :class:`whiskerframe.models.DrawText` and
:class:`whiskerframe.models.DrawRect` commands so a caller can visually verify
drawing output before sending commands to the CYD (Req 4.1). The renderer
mirrors the imagesmacker 7.0.0 anchor, coordinate, and multiline-text model
(Req 4.2) by reusing the exact placement inputs the pure
:class:`whiskerframe.builder.CommandBuilder` already resolved: every command's
``(x, y)`` anchor pixel is the value :meth:`RectangleCoordinates.anchor_coordinates`
returned, and multiline blocks stack by the same ``line_h`` advance and metrics
table (:mod:`whiskerframe.metrics`) the builder used. Placement therefore matches
device placement rather than reimplementing the anchor math differently
(Property 6, Req 8.4).

Pillow is an optional dependency (the ``preview`` extra). Its import is guarded
and lazy: importing this module never requires Pillow, and
:class:`whiskerframe.builder.CommandBuilder` stays fully operable without it.
Only when a preview function is actually invoked without Pillow installed is a
clear error raised naming the missing dependency (Req 4.4).

[← Go back to `whiskerframe`](./index.md)

<h2 id="variables"><a href="#variables">Variables</a></h2>

<h3 id="variables-default_bg_rgb565"><a href="#variables-default_bg_rgb565"><pre>DEFAULT_BG_RGB565</pre></a></h3>

```python
int
```

Default RGB565 canvas background (black), matching a cleared display.

<h3 id="variables-display_height"><a href="#variables-display_height"><pre>DISPLAY_HEIGHT</pre></a></h3>

```python
int
```

Default preview canvas height in pixels, matching the rotated ILI9341 extent.

<h3 id="variables-display_width"><a href="#variables-display_width"><pre>DISPLAY_WIDTH</pre></a></h3>

```python
int
```

Default preview canvas width in pixels, matching the rotated ILI9341 extent.

<h2 id="functions"><a href="#functions">Functions</a></h2>

<h3 id="functions-rgb565_to_rgb888"><a href="#functions-rgb565_to_rgb888"><pre>rgb565_to_rgb888</pre></a></h3>

```python
(color: int) → tuple[int, int, int]
```

Convert an RGB565 ``uint16`` color to an 8-bit-per-channel RGB triple.

Expand the packed 5-6-5 channels to the full 0-255 range by replicating the
high bits into the low bits, matching how the ILI9341 presents RGB565 pixels.
This keeps preview colors visually consistent with the device (Req 4.2).

Args:
- color (`int`): RGB565 color in ``[0, 65535]``.

Returns:
`tuple[int, int, int]`: The ``(r, g, b)`` channels, each in ``[0, 255]``.

<h2 id="classes"><a href="#classes">Classes</a></h2>

<h3 id="classes-previewrenderer"><a href="#classes-previewrenderer"><pre>PreviewRenderer</pre></a></h3>

```python
(width: int = 320, height: int = 240, background: int = 0)
```

Render resolved drawing commands to a Pillow image for host-side preview.

Draw the resolved :class:`whiskerframe.models.DrawText` and
:class:`whiskerframe.models.DrawRect` commands produced by
:class:`whiskerframe.builder.CommandBuilder` onto an RGB canvas, reusing the
commands' already-resolved anchor coordinates and the shared
:mod:`whiskerframe.metrics` table so preview placement matches device
placement exactly (Property 6, Req 4.2, 8.4). The renderer performs no anchor
math of its own beyond honoring the resolved ``(x, y)`` and packed ``anchor``
each command carries.

Pillow is imported lazily on the first draw, so constructing a renderer and
importing this module never require the ``preview`` extra; a clear error is
raised only when :meth:`render` is called without Pillow installed (Req 4.4).

Initialize the preview canvas dimensions and background color.

Args:
- width (`int`, optional): Canvas width in px. Defaults to `DISPLAY_WIDTH`.
- height (`int`, optional): Canvas height in px. Defaults to `DISPLAY_HEIGHT`.
- background (`int`, optional): RGB565 canvas fill. Defaults to `DEFAULT_BG_RGB565`.

Raises:
- `ValueError`: If ``width`` or ``height`` is not positive.

Returns:
`None`: This initializer does not return a value.

<h4 id="classes-previewrenderer-methods"><a href="#classes-previewrenderer-methods">Methods</a></h4>

<h5 id="classes-previewrenderer-methods-render"><a href="#classes-previewrenderer-methods-render"><pre>render</pre></a></h5>

```python
(self, commands: Iterable[DrawText | DrawRect]) → Image.Image
```

Render an iterable of resolved commands onto a fresh preview image.

Create the canvas, then draw each command in order using the placement
already resolved by the :class:`whiskerframe.builder.CommandBuilder`, so
preview coordinates equal the coordinates the device receives (Property 6,
Req 4.1, 4.2). Pillow is imported lazily here; without it a clear error
naming the ``preview`` extra is raised (Req 4.4).

Args:
- commands (`Iterable[DrawText | DrawRect]`): Resolved commands to draw, in z-order.

Raises:
- `RuntimeError`: If Pillow is not installed.
- `TypeError`: If a command is neither a `DrawText` nor a `DrawRect`.

Returns:
`Image.Image`: The rendered RGB preview image.

---

[← Go back to `whiskerframe`](./index.md)