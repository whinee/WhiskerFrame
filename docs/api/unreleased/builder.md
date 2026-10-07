<h1 id=""><a href="#">Module whiskerframe.builder</a></h1>

Pure command builder for the CYD Display Link (imagesmacker 7.0.0 parity).

Turn caller-facing drawing requests into fully resolved
:class:`whiskerframe.models.DrawText` and :class:`whiskerframe.models.DrawRect`
commands, ready for :func:`whiskerframe.protocol.serialize`. The
:class:`CommandBuilder` resolves the two-character ``[lmr][tmb]`` anchor to a
concrete pixel via :meth:`whiskerframe.coordinates.RectangleCoordinates.anchor_coordinates`
(Req 3.1, 3.4), stacks multiline blocks by line height so the block's anchor
point coincides with the rectangle's anchor point (Req 3.3, 8.3), and mirrors
the imagesmacker 7.0.0 anchor/coordinate/multiline signatures and behavior in
strict parity (Req 8.4).

Placement uses pure integer math and the static
:mod:`whiskerframe.metrics` table, so this module imports no Pillow (or any
imaging library) and stays usable on the serial command path (Req 3.2). When a
computed placement is inconsistent with the imagesmacker 7.0.0 model -- for
example an anchor resolving outside the target rectangle, or invalid
coordinates -- the builder rejects the command and surfaces an error to the
caller, producing no fallback or approximate placement (Req 3.5).

[← Go back to `whiskerframe`](./index.md)

<h2 id="classes"><a href="#classes">Classes</a></h2>

<h3 id="classes-commandbuilder"><a href="#classes-commandbuilder"><pre>CommandBuilder</pre></a></h3>

Build resolved drawing commands from anchor, coordinate, and geometry math.

Provide the pure host-side drawing API: :meth:`draw_text` and
:meth:`draw_rect` resolve a two-character ``[lmr][tmb]`` anchor against a
:class:`whiskerframe.coordinates.RectangleCoordinates` region and return a
validated :class:`whiskerframe.models.DrawText` or
:class:`whiskerframe.models.DrawRect` whose fields map one-to-one onto the
wire payload layouts. The builder mirrors the imagesmacker 7.0.0 API in
strict parity (Req 8.4) and imports no Pillow (Req 3.2).

The builder is stateless, so a single instance may build any number of
commands. Placement inconsistent with the imagesmacker 7.0.0 model is
rejected with an exception rather than approximated (Req 3.5).

<h4 id="classes-commandbuilder-methods"><a href="#classes-commandbuilder-methods">Methods</a></h4>

<h5 id="classes-commandbuilder-methods-draw_rect"><a href="#classes-commandbuilder-methods-draw_rect"><pre>draw_rect</pre></a></h5>

```python
(self, coords: RectangleCoordinates, *, anchor: Anchor = 'lt', color: int = 65535, filled: bool = False) → whiskerframe.models.DrawRect
```

Build a resolved ``DRAW_RECT`` command anchored within a rectangle.

Resolve ``anchor`` against ``coords`` to confirm the anchor point lies on
the region, then emit the rectangle's canonical top-left origin and
dimensions so the firmware draws from a resolved top-left datum. The
RGB565 ``color`` and ``filled`` flag are carried through unchanged. If the
resolved anchor point falls outside the ``coords`` bounding box, the
command is rejected with a `ValueError` -- no approximate placement
(Req 3.5).

Args:
- coords (`RectangleCoordinates`): Target rectangle region to draw.
- anchor (`Anchor`, optional): Two-character ``[lmr][tmb]`` anchor. Defaults to `"lt"`.
- color (`int`, optional): RGB565 color in ``[0, 65535]``. Defaults to `0xFFFF`.
- filled (`bool`, optional): Whether the rectangle is filled rather than outlined. Defaults to `False`.

Raises:
- `ValueError`: If the anchor is invalid or the resolved placement falls outside ``coords``.

Returns:
`DrawRect`: The resolved rectangle command matching the ``DRAW_RECT`` payload layout.

<h5 id="classes-commandbuilder-methods-draw_text"><a href="#classes-commandbuilder-methods-draw_text"><pre>draw_text</pre></a></h5>

```python
(self, coords: RectangleCoordinates, text: str, *, anchor: Anchor = 'mm', style: TextStyle | None = None, multiline: bool = False, line_height: int | None = None, inverted: bool = False) → whiskerframe.models.DrawText
```

Build a resolved ``DRAW_TEXT`` command anchored within a rectangle.

Resolve ``anchor`` to a pixel on ``coords`` via
:meth:`RectangleCoordinates.anchor_coordinates` (Req 3.1, 3.4). For
multiline text, split ``text`` on ``\n`` and stack the lines by
``line_height`` (defaulting to the font's
:func:`whiskerframe.metrics.line_advance`) so the block's anchor point
coincides with the rectangle's anchor point (Req 3.3, 8.3); ``inverted``
reverses the line order and swaps foreground and background, matching the
imagesmacker 7.0.0 ``inverted`` semantics. Sizing uses the pure
:mod:`whiskerframe.metrics` table -- no Pillow (Req 3.2).

If the resolved anchor point falls outside the ``coords`` bounding box,
the placement is inconsistent with the imagesmacker 7.0.0 model and the
command is rejected with a `ValueError`; no fallback or approximate
placement is produced (Req 3.5).

Args:
- coords (`RectangleCoordinates`): Target rectangle region the text is anchored within.
- text (`str`): Text to render; lines separated by ``\n`` when ``multiline``.
- anchor (`Anchor`, optional): Two-character ``[lmr][tmb]`` anchor. Defaults to `"mm"`.
- style (`TextStyle | None`, optional): Color, background, font-size, and inversion style. Defaults to a fresh `TextStyle`.
- multiline (`bool`, optional): Whether to lay the text out as stacked lines. Defaults to `False`.
- line_height (`int | None`, optional): Explicit per-line advance in px. Defaults to the font's `line_advance`.
- inverted (`bool`, optional): Whether to reverse line order and swap foreground/background. Defaults to `False`.

Raises:
- `ValueError`: If the anchor is invalid or the resolved placement falls outside ``coords``.

Returns:
`DrawText`: The resolved text command matching the ``DRAW_TEXT`` payload layout.

---

[← Go back to `whiskerframe`](./index.md)