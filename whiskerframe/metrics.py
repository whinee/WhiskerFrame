"""
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
"""

from __future__ import annotations

from typing import NamedTuple

__all__ = [
    "DEFAULT_FONT_SIZE",
    "FONT_METRICS",
    "FontMetrics",
    "TextSize",
    "line_advance",
    "line_height",
    "line_width",
    "text_height",
    "text_size",
    "text_width",
]


class FontMetrics(NamedTuple):
    """
    Fixed-cell glyph metrics for a single ``font_size`` selector.

    Every glyph in the font is treated as occupying a uniform cell, matching the
    TFT_eSPI built-in bitmap fonts. Line stacking advances by ``line_advance``,
    which may exceed ``cell_height`` to provide inter-line leading.

    Attributes:
    - cell_width (`int`): Advance width of one glyph cell, in pixels.
    - cell_height (`int`): Height of one glyph cell, in pixels.
    - line_advance (`int`): Vertical distance between successive line origins, in pixels.

    """

    cell_width: int
    cell_height: int
    line_advance: int


DEFAULT_FONT_SIZE: int = 1
"""Default ``font_size`` selector used when a caller omits one."""

FONT_METRICS: dict[int, FontMetrics] = {
    1: FontMetrics(cell_width=6, cell_height=8, line_advance=8),
    2: FontMetrics(cell_width=12, cell_height=16, line_advance=16),
    3: FontMetrics(cell_width=18, cell_height=24, line_advance=24),
    4: FontMetrics(cell_width=24, cell_height=32, line_advance=32),
}
"""Static per-``font_size`` metrics table (pure data, no Pillow).

Keys are the ``font_size`` selectors carried in the ``DRAW_TEXT`` payload; each
value is the fixed-cell `FontMetrics` for that size. Sizes scale the base
6x8 cell linearly, matching TFT_eSPI text-size multipliers.
"""


class TextSize(NamedTuple):
    """
    Pixel dimensions of a rendered text block.

    Attributes:
    - width (`int`): Width of the widest line, in pixels.
    - height (`int`): Total stacked height of all lines, in pixels.

    """

    width: int
    height: int


def _metrics_for(font_size: int) -> FontMetrics:
    """
    Return the metrics for a ``font_size`` selector.

    Args:
    - font_size (`int`): Font-size selector to look up.

    Raises:
    - `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

    Returns:
    `FontMetrics`: The fixed-cell metrics for the requested size.

    """
    try:
        return FONT_METRICS[font_size]
    except KeyError as exc:
        valid = ", ".join(str(k) for k in sorted(FONT_METRICS))
        raise KeyError(
            f"no font metrics for font_size {font_size!r}; valid sizes: {valid}",
        ) from exc


def line_width(line: str, font_size: int = DEFAULT_FONT_SIZE) -> int:
    """
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

    """
    metrics = _metrics_for(font_size)
    glyphs = len(line.replace("\n", ""))
    return glyphs * metrics.cell_width


def line_height(font_size: int = DEFAULT_FONT_SIZE) -> int:
    """
    Return the pixel height of one glyph cell.

    Args:
    - font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.

    Raises:
    - `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

    Returns:
    `int`: Height of one line's glyph cell in pixels.

    """
    return _metrics_for(font_size).cell_height


def line_advance(font_size: int = DEFAULT_FONT_SIZE) -> int:
    """
    Return the default vertical advance between successive line origins.

    This is the fallback ``line_height`` used for multiline stacking when the
    caller does not supply an explicit value.

    Args:
    - font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.

    Raises:
    - `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

    Returns:
    `int`: Vertical distance between line origins in pixels.

    """
    return _metrics_for(font_size).line_advance


def text_width(text: str, font_size: int = DEFAULT_FONT_SIZE) -> int:
    r"""
    Measure the pixel width of a (possibly multiline) text block.

    The block width is the width of its widest line. Lines are split on ``\\n``.

    Args:
    - text (`str`): Text block, with lines separated by ``\\n``.
    - font_size (`int`, optional): Font-size selector. Defaults to `DEFAULT_FONT_SIZE`.

    Raises:
    - `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

    Returns:
    `int`: Width of the widest line in pixels.

    """
    lines = text.split("\n")
    return max((line_width(line, font_size) for line in lines), default=0)


def text_height(
    text: str,
    font_size: int = DEFAULT_FONT_SIZE,
    line_height_px: int | None = None,
) -> int:
    r"""
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

    """
    metrics = _metrics_for(font_size)
    advance = metrics.line_advance if line_height_px is None else line_height_px
    count = len(text.split("\n"))
    if count <= 0:
        return 0
    return (count - 1) * advance + metrics.cell_height


def text_size(
    text: str,
    font_size: int = DEFAULT_FONT_SIZE,
    line_height_px: int | None = None,
) -> TextSize:
    r"""
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

    """
    return TextSize(
        width=text_width(text, font_size),
        height=text_height(text, font_size, line_height_px),
    )
