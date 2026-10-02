"""
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
"""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whiskerframe.metrics import FONT_METRICS
from whiskerframe.models import UINT8_MAX, UINT16_MAX

__all__ = [
    "DISPLAY_HEIGHT",
    "DISPLAY_WIDTH",
    "INT8_MAX",
    "INT8_MIN",
    "DrawCells",
    "DrawImage",
    "Scroll",
    "TerminalGeometry",
]

DISPLAY_WIDTH: int = 320
"""Visible panel width in pixels (landscape, TFT_eSPI rotation 1)."""

DISPLAY_HEIGHT: int = 240
"""Visible panel height in pixels (landscape, TFT_eSPI rotation 1)."""

INT8_MIN: int = -128
"""Minimum value of a signed ``int8`` wire field."""

INT8_MAX: int = 127
"""Maximum value of a signed ``int8`` wire field."""

_MAX_CELL_TEXT: int = UINT16_MAX
"""Maximum number of cells (characters) a single ``DRAW_CELLS`` run may carry."""


class TerminalGeometry(NamedTuple):
    """
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

    """

    cols: int
    rows: int
    cell_w: int
    cell_h: int

    @classmethod
    def for_font_size(cls, font_size: int) -> TerminalGeometry:
        """
        Compute the grid geometry for a ``font_size`` selector.

        Look up the fixed-cell metrics for ``font_size`` and floor-divide the
        320x240 panel by the cell width/height to get the column and row counts.

        Args:
        - font_size (`int`): Font-size selector indexing `FONT_METRICS`.

        Raises:
        - `KeyError`: If ``font_size`` has no entry in `FONT_METRICS`.

        Returns:
        `TerminalGeometry`: The grid dimensions and cell size for the font.

        """
        try:
            metrics = FONT_METRICS[font_size]
        except KeyError as exc:
            valid = ", ".join(str(key) for key in sorted(FONT_METRICS))
            msg = f"no font metrics for font_size {font_size!r}; valid sizes: {valid}"
            raise KeyError(msg) from exc
        return cls(
            cols=DISPLAY_WIDTH // metrics.cell_width,
            rows=DISPLAY_HEIGHT // metrics.cell_height,
            cell_w=metrics.cell_width,
            cell_h=metrics.cell_height,
        )


class DrawCells(BaseModel):
    """
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

    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    col: int = Field(ge=0, le=UINT16_MAX)
    row: int = Field(ge=0, le=UINT16_MAX)
    fg: int = Field(ge=0, le=UINT16_MAX)
    bg: int = Field(ge=0, le=UINT16_MAX)
    font_size: int = Field(ge=0, le=UINT8_MAX)
    text: str = Field(default="", max_length=_MAX_CELL_TEXT)


class Scroll(BaseModel):
    """
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

    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows: int = Field(ge=INT8_MIN, le=INT8_MAX)
    fill: int = Field(ge=0, le=UINT16_MAX)
    top: int = Field(ge=0, le=UINT16_MAX)
    bottom: int = Field(ge=0, le=UINT16_MAX)


class DrawImage(BaseModel):
    """
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

    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: int = Field(ge=0, le=UINT16_MAX)
    y: int = Field(ge=0, le=UINT16_MAX)
    w: int = Field(ge=0, le=UINT16_MAX)
    h: int = Field(ge=0, le=UINT16_MAX)
    data: bytes = b""

    @model_validator(mode="after")
    def _check_data_length(self) -> DrawImage:
        """
        Validate that ``data`` holds exactly ``w * h * 2`` RGB565 bytes.

        Raises:
        - `ValueError`: If ``len(data)`` does not equal ``w * h * 2``.

        Returns:
        `DrawImage`: The validated model instance.

        """
        expected = self.w * self.h * 2
        if len(self.data) != expected:
            msg = (
                f"DRAW_IMAGE data length mismatch: {len(self.data)} bytes "
                f"!= w*h*2 = {expected} bytes."
            )
            raise ValueError(msg)
        return self
