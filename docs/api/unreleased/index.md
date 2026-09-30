Module whiskerframe
===================
whiskerframe: pure command builder for the CYD Display Link.

Expose the public host-side drawing API: rectangle coordinate types, the anchor
type, command models, the :class:`CommandBuilder`, and the wire
:func:`serialize` function. Importing this package pulls in only the pure command
path; the optional Pillow-based ``preview`` renderer and the pyserial
``transport`` are not imported here, so ``whiskerframe`` stays importable without
either optional dependency installed.

Sub-modules
-----------
* whiskerframe.anchors
* whiskerframe.builder
* whiskerframe.coordinates
* whiskerframe.metrics
* whiskerframe.models
* whiskerframe.preview
* whiskerframe.protocol
* whiskerframe.transport

Functions
---------

`serialize(command: DrawText | DrawRect) ‑> bytes`
:   Serialize a resolved drawing command into complete framed bytes.
    
    Encode the command's opcode-specific payload and wrap it in the
    ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame via :func:`frame`. The result is
    ready for transmission over the USB-serial link (Req 1.1) and carries no
    framebuffer or full-display bitmap (Req 1.5).
    
    Args:
    - command (`DrawText | DrawRect`): Resolved command to serialize.
    
    Raises:
    - `TypeError`: If ``command`` is neither a `DrawText` nor a `DrawRect`.
    
    Returns:
    `bytes`: The complete framed byte sequence.

Classes
-------

`CommandBuilder()`
:   Build resolved drawing commands from anchor, coordinate, and geometry math.
    
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

    ### Methods

    `draw_rect(self, coords: RectangleCoordinates, *, anchor: Anchor = 'lt', color: int = 65535, filled: bool = False) ‑> whiskerframe.models.DrawRect`
    :   Build a resolved ``DRAW_RECT`` command anchored within a rectangle.
        
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

    `draw_text(self, coords: RectangleCoordinates, text: str, *, anchor: Anchor = 'mm', style: TextStyle | None = None, multiline: bool = False, line_height: int | None = None, inverted: bool = False) ‑> whiskerframe.models.DrawText`
    :   Build a resolved ``DRAW_TEXT`` command anchored within a rectangle.
        
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

`DrawRect(**data: Any)`
:   Resolved ``DRAW_RECT`` (``0x02``) command matching the wire payload layout.
    
    Hold the fully resolved fields the serializer encodes into a ``DRAW_RECT``
    payload: the host-resolved top-left pixel ``(x, y)``, the ``(w, h)``
    dimensions (all ``uint16``), the RGB565 ``color`` (``uint16``), and the
    ``filled`` flag bit packed into the payload's ``uint8`` flags byte. Anchor
    resolution happens host-side, so ``(x, y)`` is already the top-left origin
    ready for little-endian serialization.
    
    The model is validated on construction (pydantic v2): coordinates,
    dimensions, and color are bounded to ``uint16``, so an out-of-range value is
    rejected before it reaches the wire.
    
    Attributes:
    - x (`int`): Resolved top-left x pixel in ``[0, 65535]``.
    - y (`int`): Resolved top-left y pixel in ``[0, 65535]``.
    - w (`int`): Rectangle width in ``[0, 65535]`` px.
    - h (`int`): Rectangle height in ``[0, 65535]`` px.
    - color (`int`): RGB565 color in ``[0, 65535]``.
    - filled (`bool`): Whether the rectangle is filled rather than outlined.
    
    Create a new model by parsing and validating input data from keyword arguments.
    
    Raises [`ValidationError`][pydantic_core.ValidationError] if the input data cannot be
    validated to form a valid model.
    
    `self` is explicitly positional-only to allow `self` as a field name.

    ### Ancestors (in MRO)

    * pydantic.main.BaseModel

    ### Class variables

    `color: int`
    :   The type of the None singleton.

    `filled: bool`
    :   The type of the None singleton.

    `h: int`
    :   The type of the None singleton.

    `model_config`
    :   The type of the None singleton.

    `w: int`
    :   The type of the None singleton.

    `x: int`
    :   The type of the None singleton.

    `y: int`
    :   The type of the None singleton.

`DrawText(**data: Any)`
:   Resolved ``DRAW_TEXT`` (``0x01``) command matching the wire payload layout.
    
    Hold the fully resolved fields the serializer encodes into a ``DRAW_TEXT``
    payload: the host-resolved anchor pixel ``(x, y)`` (both ``uint16``), the
    packed ``anchor`` byte source, RGB565 ``color`` and ``bg_color`` (``uint16``),
    the ``uint8`` ``font_size`` selector, the ``inverted`` and ``multiline`` flag
    bits, the ``line_h`` per-line advance (``uint16``), and the UTF-8 ``text``.
    All coordinate math and anchor resolution happen host-side before this model
    is built, so the fields are ready for direct little-endian serialization.
    
    The model is validated on construction (pydantic v2): coordinates, colors,
    and ``line_h`` are bounded to ``uint16`` and ``font_size`` to ``uint8``, so an
    out-of-range value is rejected before it reaches the wire.
    
    Attributes:
    - x (`int`): Resolved anchor x pixel in ``[0, 65535]``.
    - y (`int`): Resolved anchor y pixel in ``[0, 65535]``.
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor for the text datum.
    - color (`int`): RGB565 foreground color in ``[0, 65535]``.
    - bg_color (`int`): RGB565 background color in ``[0, 65535]``.
    - font_size (`int`): ``uint8`` font-size selector in ``[0, 255]``.
    - inverted (`bool`): Whether foreground and background are swapped.
    - multiline (`bool`): Whether the text is laid out as stacked lines.
    - line_h (`int`): Per-line vertical advance in ``[0, 65535]`` px.
    - text (`str`): UTF-8 text (LF-separated lines when multiline).
    
    Create a new model by parsing and validating input data from keyword arguments.
    
    Raises [`ValidationError`][pydantic_core.ValidationError] if the input data cannot be
    validated to form a valid model.
    
    `self` is explicitly positional-only to allow `self` as a field name.

    ### Ancestors (in MRO)

    * pydantic.main.BaseModel

    ### Class variables

    `anchor: Literal['lt', 'mt', 'rt', 'lm', 'mm', 'rm', 'lb', 'mb', 'rb']`
    :   The type of the None singleton.

    `bg_color: int`
    :   The type of the None singleton.

    `color: int`
    :   The type of the None singleton.

    `font_size: int`
    :   The type of the None singleton.

    `inverted: bool`
    :   The type of the None singleton.

    `line_h: int`
    :   The type of the None singleton.

    `model_config`
    :   The type of the None singleton.

    `multiline: bool`
    :   The type of the None singleton.

    `text: str`
    :   The type of the None singleton.

    `x: int`
    :   The type of the None singleton.

    `y: int`
    :   The type of the None singleton.

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

`TextStyle(**data: Any)`
:   Presentation style for a text command, mirroring imagesmacker text styling.
    
    Capture the color, background color, font-size selector, and inversion flag
    used to render text. Colors are RGB565 ``uint16`` values matching the ILI9341
    native pixel format; ``font_size`` is the ``uint8`` selector indexing the
    static `whiskerframe.metrics.FONT_METRICS` table. When ``inverted`` is set,
    the firmware swaps foreground and background, matching imagesmacker's
    ``inverted`` semantics.
    
    The model is validated on construction (pydantic v2) and rejects extra
    fields, so an out-of-range color or size is caught before serialization.
    
    Attributes:
    - color (`int`): RGB565 foreground color in ``[0, 65535]``.
    - bg_color (`int`): RGB565 background color in ``[0, 65535]`` (used when inverted).
    - font_size (`int`): ``uint8`` font-size selector in ``[0, 255]``.
    - inverted (`bool`): Whether to swap foreground and background.
    
    Create a new model by parsing and validating input data from keyword arguments.
    
    Raises [`ValidationError`][pydantic_core.ValidationError] if the input data cannot be
    validated to form a valid model.
    
    `self` is explicitly positional-only to allow `self` as a field name.

    ### Ancestors (in MRO)

    * pydantic.main.BaseModel

    ### Descendants

    * whiskerframe.models.TextConfig

    ### Class variables

    `bg_color: int`
    :   The type of the None singleton.

    `color: int`
    :   The type of the None singleton.

    `font_size: int`
    :   The type of the None singleton.

    `inverted: bool`
    :   The type of the None singleton.

    `model_config`
    :   The type of the None singleton.

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