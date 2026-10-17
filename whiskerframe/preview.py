from __future__ import annotations

"""
Optional Pillow-based host-side preview renderer for the CYD Display Link.

Render a host-side image of resolved :class:`whiskerframe.models.DrawText`,
:class:`whiskerframe.models.DrawRect`, :class:`whiskerframe.terminal.DrawCells`,
:class:`whiskerframe.terminal.Scroll`, and :class:`whiskerframe.terminal.DrawImage`
commands so a caller can visually verify drawing output before sending commands
to the CYD (Req 4.1). The renderer mirrors the protocol anchor, coordinate,
and multiline-text model (Req 4.2) by reusing the exact placement inputs the pure
:class:`whiskerframe.builder.CommandBuilder` and terminal bridge already resolved.
Clearly labels physical device capture versus host reconstruction from authoritative
ordered display updates (since the hardware protocol is write-only over serial/UART).

Pillow is an optional dependency (the ``preview`` extra). Its import is guarded
and lazy: importing this module never requires Pillow, and command models stay
fully operable without it. Only when a preview function is actually invoked without
Pillow installed is a clear error raised naming the missing dependency (Req 4.4).
"""

__all__ = [
    "DEFAULT_BG_RGB565",
    "DISPLAY_HEIGHT",
    "DISPLAY_WIDTH",
    "PreviewRenderer",
    "rgb565_to_rgb888",
]

import struct
from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from whiskerframe.anchors import resolve_anchor
from whiskerframe.metrics import FONT_METRICS
from whiskerframe.metrics import line_height as glyph_height
from whiskerframe.metrics import line_width
from whiskerframe.models import DrawRect, DrawText
from whiskerframe.terminal import DrawCells, DrawImage, Scroll

if TYPE_CHECKING:
    from PIL import Image

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

    Draw resolved :class:`whiskerframe.models.DrawText`, :class:`whiskerframe.models.DrawRect`,
    :class:`whiskerframe.terminal.DrawCells`, :class:`whiskerframe.terminal.Scroll`,
    and :class:`whiskerframe.terminal.DrawImage` commands onto an RGB canvas, reconstructing
    display state from authoritative ordered display updates (write-only hardware protocol).
    """

    def __init__(
        self,
        width: int = DISPLAY_WIDTH,
        height: int = DISPLAY_HEIGHT,
        background: int = DEFAULT_BG_RGB565,
    ) -> None:
        if width <= 0 or height <= 0:
            msg = f"Canvas dimensions must be positive, got {width}x{height}."
            raise ValueError(msg)
        self.width = width
        self.height = height
        self.background = background
        self.active_cell_height = 8  # Default size-1 cell height

    def draw_command(
        self,
        image: 'Image.Image',
        command: DrawText | DrawRect | DrawCells | Scroll | DrawImage,
    ) -> 'Image.Image':
        """
        Draw a single resolved command onto an existing Pillow image buffer.

        Args:
        - image (`Image.Image`): Target Pillow RGB image.
        - command (`DrawText | DrawRect | DrawCells | Scroll | DrawImage`): Resolved command.

        Returns:
        `Image.Image`: The updated image.
        """
        image_module = _require_pillow()
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        self._draw_command(draw, command)
        return cast("Image.Image", image)

    def render(self, commands: Iterable[DrawText | DrawRect | DrawCells | Scroll | DrawImage]) -> 'Image.Image':
        image_module = _require_pillow()
        image = image_module.new(
            "RGB",
            (self.width, self.height),
            rgb565_to_rgb888(self.background),
        )
        for command in commands:
            self.draw_command(image, command)
        return cast("Image.Image", image)

    def _draw_command(self, draw: object, command: DrawText | DrawRect | DrawCells | Scroll | DrawImage) -> None:
        if isinstance(command, DrawText):
            self._draw_text(draw, command)
        elif isinstance(command, DrawRect):
            self._draw_rect(draw, command)
        elif isinstance(command, DrawCells):
            self._draw_cells(draw, command)
        elif isinstance(command, Scroll):
            self._draw_scroll(draw, command)
        elif isinstance(command, DrawImage):
            self._draw_image(draw, command)
        else:
            msg = f"Cannot preview object of type {type(command).__name__!r}."
            raise TypeError(msg)

    def _draw_rect(self, draw: object, command: DrawRect) -> None:
        color = rgb565_to_rgb888(command.color)
        x2 = command.x + command.w
        y2 = command.y + command.h
        box = (command.x, command.y, x2, y2)
        if command.filled:
            draw.rectangle(box, fill=color)
        else:
            draw.rectangle(box, outline=color)

    def _draw_text(self, draw: object, command: DrawText) -> None:
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
            if not line:
                continue
            draw.text((origin_x, origin_y), line, fill=fill)

    def _draw_cells(self, draw: object, command: DrawCells) -> None:
        metrics = FONT_METRICS.get(command.font_size, FONT_METRICS[1])
        cell_w = metrics.cell_width
        cell_h = metrics.cell_height
        self.active_cell_height = cell_h

        base_x = command.col * cell_w
        base_y = command.row * cell_h
        if base_y < 0 or base_y >= self.height or base_x >= self.width:
            return

        run_px = len(command.text) * cell_w
        bg_w = min(run_px, self.width - base_x)
        if bg_w > 0:
            bg_color = rgb565_to_rgb888(command.bg)
            draw.rectangle((base_x, base_y, base_x + bg_w, base_y + cell_h), fill=bg_color)

        fg_color = rgb565_to_rgb888(command.fg)

        for i, ch in enumerate(command.text):
            cx = base_x + i * cell_w
            if cx >= self.width:
                break
            if ch != ' ' and ch != '\0':
                draw.text((cx, base_y), ch, fill=fg_color)

    def _draw_scroll(self, draw: object, command: Scroll) -> None:
        if command.bottom < command.top:
            return
        cell_h = self.active_cell_height
        band_top = max(0, command.top * cell_h)
        band_bottom = min(self.height, (command.bottom + 1) * cell_h)
        band_h = band_bottom - band_top
        if band_h <= 0:
            return

        shift = (abs(command.rows)) * cell_h
        fill_color = rgb565_to_rgb888(command.fill)

        image = draw._image  # type: ignore
        if command.rows == 0 or shift >= band_h:
            draw.rectangle((0, band_top, self.width, band_bottom), fill=fill_color)
            return

        if command.rows > 0:
            # Scroll up
            box = (0, band_top + shift, self.width, band_bottom)
            region = image.crop(box)
            image.paste(region, (0, band_top))
            draw.rectangle((0, band_bottom - shift, self.width, band_bottom), fill=fill_color)
        else:
            # Scroll down
            box = (0, band_top, self.width, band_bottom - shift)
            region = image.crop(box)
            image.paste(region, (0, band_top + shift))
            draw.rectangle((0, band_top, self.width, band_top + shift), fill=fill_color)

    def _draw_image(self, draw: object, command: DrawImage) -> None:
        image = draw._image  # type: ignore
        w = command.w
        h = command.h
        if w == 0 or h == 0 or len(command.data) < w * h * 2:
            return
        pixels = struct.unpack(f"<{w * h}H", command.data[:w * h * 2])
        rgb888_bytes = bytearray(w * h * 3)
        for i, p in enumerate(pixels):
            r8, g8, b8 = rgb565_to_rgb888(p)
            rgb888_bytes[i * 3] = r8
            rgb888_bytes[i * 3 + 1] = g8
            rgb888_bytes[i * 3 + 2] = b8
        from PIL import Image as PILImage
        patch = PILImage.frombytes("RGB", (w, h), bytes(rgb888_bytes))
        image.paste(patch, (command.x, command.y))

    @staticmethod
    def _line_origin(
        command: DrawText,
        line: str,
        row: int,
        advance: int,
        cell_height: int,
    ) -> tuple[int, int]:
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
