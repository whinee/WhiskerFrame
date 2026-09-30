r"""
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
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from whiskerframe.anchors import resolve_anchor
from whiskerframe.metrics import line_height as glyph_height
from whiskerframe.metrics import line_width
from whiskerframe.models import DrawRect, DrawText

if TYPE_CHECKING:
    from PIL import Image

__all__ = [
    "DEFAULT_BG_RGB565",
    "DISPLAY_HEIGHT",
    "DISPLAY_WIDTH",
    "PreviewRenderer",
    "rgb565_to_rgb888",
]

DISPLAY_WIDTH: int = 320
"""Default preview canvas width in pixels, matching the rotated ILI9341 extent."""

DISPLAY_HEIGHT: int = 240
"""Default preview canvas height in pixels, matching the rotated ILI9341 extent."""

DEFAULT_BG_RGB565: int = 0x0000
"""Default RGB565 canvas background (black), matching a cleared display."""

_PILLOW_HINT: str = (
    "Pillow is required for preview; install the 'preview' extra: "
    "pip install whiskerframe[preview]"
)


def rgb565_to_rgb888(color: int) -> tuple[int, int, int]:
    """
    Convert an RGB565 ``uint16`` color to an 8-bit-per-channel RGB triple.

    Expand the packed 5-6-5 channels to the full 0-255 range by replicating the
    high bits into the low bits, matching how the ILI9341 presents RGB565 pixels.
    This keeps preview colors visually consistent with the device (Req 4.2).

    Args:
    - color (`int`): RGB565 color in ``[0, 65535]``.

    Returns:
    `tuple[int, int, int]`: The ``(r, g, b)`` channels, each in ``[0, 255]``.

    """
    r5 = (color >> 11) & 0x1F
    g6 = (color >> 5) & 0x3F
    b5 = color & 0x1F
    r8 = (r5 << 3) | (r5 >> 2)
    g8 = (g6 << 2) | (g6 >> 4)
    b8 = (b5 << 3) | (b5 >> 2)
    return r8, g8, b8


def _require_pillow() -> object:
    """
    Import and return the Pillow ``Image`` module, guarding the optional import.

    Perform the Pillow import lazily so importing :mod:`whiskerframe.preview`
    never hard-fails when the ``preview`` extra is absent (Req 4.4). Raise a clear
    error naming the missing dependency only when a preview function is actually
    invoked without Pillow installed.

    Raises:
    - `RuntimeError`: If Pillow is not importable, naming the ``preview`` extra.

    Returns:
    `object`: The imported ``PIL.Image`` module.

    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - exercised only without Pillow
        raise RuntimeError(_PILLOW_HINT) from exc
    return Image


class PreviewRenderer:
    """
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
    """

    def __init__(
        self,
        width: int = DISPLAY_WIDTH,
        height: int = DISPLAY_HEIGHT,
        background: int = DEFAULT_BG_RGB565,
    ) -> None:
        """
        Initialize the preview canvas dimensions and background color.

        Args:
        - width (`int`, optional): Canvas width in px. Defaults to `DISPLAY_WIDTH`.
        - height (`int`, optional): Canvas height in px. Defaults to `DISPLAY_HEIGHT`.
        - background (`int`, optional): RGB565 canvas fill. Defaults to `DEFAULT_BG_RGB565`.

        Raises:
        - `ValueError`: If ``width`` or ``height`` is not positive.

        Returns:
        `None`: This initializer does not return a value.

        """
        if width <= 0 or height <= 0:
            msg = f"Canvas dimensions must be positive, got {width}x{height}."
            raise ValueError(msg)
        self.width = width
        self.height = height
        self.background = background

    def render(self, commands: Iterable[DrawText | DrawRect]) -> Image.Image:
        """
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

        """
        image_module = _require_pillow()
        from PIL import ImageDraw

        image = image_module.new(
            "RGB",
            (self.width, self.height),
            rgb565_to_rgb888(self.background),
        )
        draw = ImageDraw.Draw(image)
        for command in commands:
            self._draw_command(draw, command)
        return cast("Image.Image", image)

    def _draw_command(self, draw: object, command: DrawText | DrawRect) -> None:
        """
        Dispatch a single resolved command to its Pillow drawing routine.

        Args:
        - draw (`object`): The Pillow ``ImageDraw.ImageDraw`` target.
        - command (`DrawText | DrawRect`): Resolved command to draw.

        Raises:
        - `TypeError`: If ``command`` is neither a `DrawText` nor a `DrawRect`.

        Returns:
        `None`: This method draws in place and returns nothing.

        """
        if isinstance(command, DrawText):
            self._draw_text(draw, command)
        elif isinstance(command, DrawRect):
            self._draw_rect(draw, command)
        else:
            msg = f"Cannot preview object of type {type(command).__name__!r}."
            raise TypeError(msg)

    def _draw_rect(self, draw: object, command: DrawRect) -> None:
        """
        Draw a resolved ``DrawRect`` onto the canvas.

        Use the command's resolved top-left origin and dimensions directly, so the
        rectangle occupies the same pixels the firmware would draw. A filled
        rectangle fills the RGB565 color; an outline strokes it.

        Args:
        - draw (`object`): The Pillow ``ImageDraw.ImageDraw`` target.
        - command (`DrawRect`): Resolved rectangle command.

        Returns:
        `None`: This method draws in place and returns nothing.

        """
        color = rgb565_to_rgb888(command.color)
        x2 = command.x + command.w
        y2 = command.y + command.h
        box = (command.x, command.y, x2, y2)
        if command.filled:
            draw.rectangle(box, fill=color)
        else:
            draw.rectangle(box, outline=color)

    def _draw_text(self, draw: object, command: DrawText) -> None:
        """
        Draw a resolved ``DrawText`` onto the canvas, honoring multiline stacking.

        Reuse the command's resolved anchor pixel ``(x, y)`` and packed ``anchor``
        to compute each line's origin exactly as the on-device renderer does:
        single-line text is placed with its anchor point at ``(x, y)``; multiline
        text stacks lines by ``line_h`` under the same block anchor. Line widths
        and heights come from the shared :mod:`whiskerframe.metrics` table, so the
        preview reuses the builder's sizing rather than reimplementing it
        (Property 6, Req 4.2).

        Args:
        - draw (`object`): The Pillow ``ImageDraw.ImageDraw`` target.
        - command (`DrawText`): Resolved text command.

        Returns:
        `None`: This method draws in place and returns nothing.

        """
        fill = rgb565_to_rgb888(command.color)
        lines = command.text.split("\n")
        cell_height = glyph_height(command.font_size)
        advance = command.line_h if command.multiline else cell_height
        for row, line in enumerate(lines):
            origin_x, origin_y = self._line_origin(
                command,
                line,
                row,
                advance,
                cell_height,
            )
            draw.text((origin_x, origin_y), line, fill=fill)

    @staticmethod
    def _line_origin(
        command: DrawText,
        line: str,
        row: int,
        advance: int,
        cell_height: int,
    ) -> tuple[int, int]:
        """
        Compute a single line's top-left origin under the resolved block anchor.

        Mirror the builder/device placement: the block's anchor point is the
        resolved ``(command.x, command.y)``. The horizontal key shifts the line
        left/center/right of ``command.x`` by its measured width, the vertical key
        shifts the whole block up/middle/down of ``command.y`` by its stacked
        height, and ``row * advance`` offsets each successive line. All math is the
        pure integer floor-division used by :mod:`whiskerframe.metrics` and
        :mod:`whiskerframe.coordinates`.

        Args:
        - command (`DrawText`): Resolved text command carrying the anchor and origin.
        - line (`str`): The single line being placed.
        - row (`int`): Zero-based line index within the block.
        - advance (`int`): Per-line vertical advance in px.
        - cell_height (`int`): Glyph cell height in px for the font size.

        Returns:
        `tuple[int, int]`: The ``(x, y)`` top-left origin for this line.

        """
        horizontal, vertical = resolve_anchor(command.anchor)
        width = line_width(line, command.font_size)
        block_height = (len(command.text.split("\n")) - 1) * advance + cell_height

        if horizontal == "l":
            origin_x = command.x
        elif horizontal == "m":
            origin_x = command.x - width // 2
        else:  # "r"
            origin_x = command.x - width

        if vertical == "t":
            block_top = command.y
        elif vertical == "m":
            block_top = command.y - block_height // 2
        else:  # "b"
            block_top = command.y - block_height

        return origin_x, block_top + row * advance
