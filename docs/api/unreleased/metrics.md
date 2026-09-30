Module whiskerframe.metrics
===========================
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

Variables
---------

`DEFAULT_FONT_SIZE: int`
:   Default ``font_size`` selector used when a caller omits one.

`FONT_METRICS: dict[int, whiskerframe.metrics.FontMetrics]`
:   Static per-``font_size`` metrics table (pure data, no Pillow).
    
    Keys are the ``font_size`` selectors carried in the ``DRAW_TEXT`` payload; each
    value is the fixed-cell `FontMetrics` for that size. Sizes scale the base
    6x8 cell linearly, matching TFT_eSPI text-size multipliers.

Functions
---------

`line_advance(font_size: int = 1) ‑> int`
:   Return the default vertical advance between successive line origins.
    
    This is the fallback ``line_height`` used for multiline stacking when the
    caller does not supply an explicit value.
    
    Args:
    - font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.
    
    Raises:
    - `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.
    
    Returns:
    `int`: Vertical distance between line origins in pixels.

`line_height(font_size: int = 1) ‑> int`
:   Return the pixel height of one glyph cell.
    
    Args:
    - font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.
    
    Raises:
    - `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.
    
    Returns:
    `int`: Height of one line's glyph cell in pixels.

`line_width(line: str, font_size: int = 1) ‑> int`
:   Measure the pixel width of a single line of text.
    
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

`text_height(text: str, font_size: int = 1, line_height_px: int | None = None) ‑> int`
:   Measure the stacked pixel height of a (possibly multiline) text block.
    
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

`text_size(text: str, font_size: int = 1, line_height_px: int | None = None) ‑> whiskerframe.metrics.TextSize`
:   Measure the pixel dimensions of a (possibly multiline) text block.
    
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

`text_width(text: str, font_size: int = 1) ‑> int`
:   Measure the pixel width of a (possibly multiline) text block.
    
    The block width is the width of its widest line. Lines are split on ``\\n``.
    
    Args:
    - text (`str`): Text block, with lines separated by ``\\n``.
    - font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.
    
    Raises:
    - `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.
    
    Returns:
    `int`: Width of the widest line in pixels.

Classes
-------

`FontMetrics(cell_width: ForwardRef('int'), cell_height: ForwardRef('int'), line_advance: ForwardRef('int'))`
:   Fixed-cell glyph metrics for a single ``font_size`` selector.
    
    Every glyph in the font is treated as occupying a uniform cell, matching the
    TFT_eSPI built-in bitmap fonts. Line stacking advances by ``line_advance``,
    which may exceed ``cell_height`` to provide inter-line leading.
    
    Attributes:
    - cell_width (`int`): Advance width of one glyph cell, in pixels.
    - cell_height (`int`): Height of one glyph cell, in pixels.
    - line_advance (`int`): Vertical distance between successive line origins, in pixels.

    ### Ancestors (in MRO)

    * builtins.tuple

    ### Instance variables

    `cell_height: int`
    :   Alias for field number 1

    `cell_width: int`
    :   Alias for field number 0

    `line_advance: int`
    :   Alias for field number 2

`TextSize(width: ForwardRef('int'), height: ForwardRef('int'))`
:   Pixel dimensions of a rendered text block.
    
    Attributes:
    - width (`int`): Width of the widest line, in pixels.
    - height (`int`): Total stacked height of all lines, in pixels.

    ### Ancestors (in MRO)

    * builtins.tuple

    ### Instance variables

    `height: int`
    :   Alias for field number 1

    `width: int`
    :   Alias for field number 0