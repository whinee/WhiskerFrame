"""
Pydantic command models for the CYD Display Link wire protocol.

Define the validated, serialization-ready command models the `Command_Builder`
produces and the `whiskerframe.protocol` serializer encodes onto the USB-serial
link: :class:`TextStyle`, :class:`TextConfig`, and :class:`RectConfig` capture
the presentation options a caller supplies, while :class:`DrawText` and
:class:`DrawRect` are the fully resolved commands whose fields map one-to-one
onto the ``DRAW_TEXT`` (``0x01``) and ``DRAW_RECT`` (``0x02``) payload layouts.

Every field range mirrors the wire encoding described in the design's payload
tables: coordinates and dimensions are ``uint16`` (0-65535), colors are RGB565
``uint16`` (also 0-65535), the ``font_size`` selector is ``uint8`` (0-255), and
the packed flag bits (``inverted``, ``multiline`` / ``filled``) are booleans the
serializer packs into a single ``uint8`` flags byte. The ``anchor`` field carries
the two-character :data:`whiskerframe.anchors.Anchor` value so the firmware can
reconstruct the TFT_eSPI text datum from the resolved coordinates.

These models validate at construction time (pydantic v2), so an out-of-range
coordinate, color, or font-size selector is rejected before it can reach the
serializer or the device. This module is pure: it imports no Pillow (or any
imaging library) and stays usable on the serial command path.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from whiskerframe.anchors import DEFAULT_ANCHOR, Anchor
from whiskerframe.metrics import DEFAULT_FONT_SIZE

__all__ = [
    "UINT8_MAX",
    "UINT16_MAX",
    "DrawRect",
    "DrawText",
    "RectConfig",
    "TextConfig",
    "TextStyle",
]

UINT8_MAX: int = 0xFF
"""Maximum value of a ``uint8`` wire field (255)."""

UINT16_MAX: int = 0xFFFF
"""Maximum value of a ``uint16`` wire field (65535), including RGB565 colors."""

WHITE_RGB565: int = 0xFFFF
"""RGB565 white; the default foreground color."""

BLACK_RGB565: int = 0x0000
"""RGB565 black; the default background color."""


class TextStyle(BaseModel):
    """
    Presentation style for a text command, mirroring imagesmacker text styling.

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

    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    color: int = Field(default=WHITE_RGB565, ge=0, le=UINT16_MAX)
    bg_color: int = Field(default=BLACK_RGB565, ge=0, le=UINT16_MAX)
    font_size: int = Field(default=DEFAULT_FONT_SIZE, ge=0, le=UINT8_MAX)
    inverted: bool = False


class TextConfig(TextStyle):
    r"""
    Full text-command configuration: style plus anchor and multiline layout.

    Extend :class:`TextStyle` with the anchor and multiline-layout options a
    caller supplies to a text-drawing operation. ``anchor`` is the two-character
    `whiskerframe.anchors.Anchor` used to pin the text block; ``multiline``
    enables line splitting on ``\\n`` with per-line stacking; ``line_height`` is
    the optional explicit per-line vertical advance (``uint16``), defaulting to
    the font's advance when omitted.

    Attributes:
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor. Defaults to ``"mm"``.
    - multiline (`bool`): Whether the text is laid out as stacked lines.
    - line_height (`int | None`): Optional per-line advance in ``[0, 65535]`` px.

    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor: Anchor = DEFAULT_ANCHOR
    multiline: bool = False
    line_height: int | None = Field(default=None, ge=0, le=UINT16_MAX)


class RectConfig(BaseModel):
    """
    Configuration for a rectangle-drawing operation.

    Capture the anchor, color, and fill style a caller supplies to a rectangle
    operation. ``anchor`` is the two-character `whiskerframe.anchors.Anchor`
    used to pin the rectangle (default ``"lt"`` top-left); ``color`` is an RGB565
    ``uint16``; ``filled`` selects a filled rectangle rather than an outline.

    Attributes:
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor. Defaults to ``"lt"``.
    - color (`int`): RGB565 color in ``[0, 65535]``.
    - filled (`bool`): Whether the rectangle is filled rather than outlined.

    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor: Anchor = "lt"
    color: int = Field(default=WHITE_RGB565, ge=0, le=UINT16_MAX)
    filled: bool = False


class DrawText(BaseModel):
    """
    Resolved ``DRAW_TEXT`` (``0x01``) command matching the wire payload layout.

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

    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: int = Field(ge=0, le=UINT16_MAX)
    y: int = Field(ge=0, le=UINT16_MAX)
    anchor: Anchor = DEFAULT_ANCHOR
    color: int = Field(default=WHITE_RGB565, ge=0, le=UINT16_MAX)
    bg_color: int = Field(default=BLACK_RGB565, ge=0, le=UINT16_MAX)
    font_size: int = Field(default=DEFAULT_FONT_SIZE, ge=0, le=UINT8_MAX)
    inverted: bool = False
    multiline: bool = False
    line_h: int = Field(default=0, ge=0, le=UINT16_MAX)
    text: str = ""


class DrawRect(BaseModel):
    """
    Resolved ``DRAW_RECT`` (``0x02``) command matching the wire payload layout.

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

    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: int = Field(ge=0, le=UINT16_MAX)
    y: int = Field(ge=0, le=UINT16_MAX)
    w: int = Field(ge=0, le=UINT16_MAX)
    h: int = Field(ge=0, le=UINT16_MAX)
    color: int = Field(default=WHITE_RGB565, ge=0, le=UINT16_MAX)
    filled: bool = False
