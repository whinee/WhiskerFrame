"""
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
"""

from __future__ import annotations

from whiskerframe.anchors import DEFAULT_ANCHOR, Anchor
from whiskerframe.coordinates import RectangleCoordinates
from whiskerframe.metrics import line_advance
from whiskerframe.models import DrawRect, DrawText, TextStyle

__all__ = [
    "CommandBuilder",
]

_RECT_DEFAULT_ANCHOR: Anchor = "lt"
_RECT_DEFAULT_COLOR: int = 0xFFFF


class CommandBuilder:
    """
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
    """

    def draw_text(
        self,
        coords: RectangleCoordinates,
        text: str,
        *,
        anchor: Anchor = DEFAULT_ANCHOR,
        style: TextStyle | None = None,
        multiline: bool = False,
        line_height: int | None = None,
        inverted: bool = False,
    ) -> DrawText:
        r"""
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

        """
        resolved_style = style if style is not None else TextStyle()
        is_inverted = inverted or resolved_style.inverted
        advance = self._resolve_line_height(line_height, resolved_style.font_size)
        content = self._layout_text(text, multiline=multiline, inverted=is_inverted)

        origin = coords.anchor_coordinates(anchor)
        self._reject_out_of_bounds(coords, origin.x, origin.y)

        fg, bg = self._resolve_colors(resolved_style, inverted=is_inverted)
        return DrawText(
            x=origin.x,
            y=origin.y,
            anchor=anchor,
            color=fg,
            bg_color=bg,
            font_size=resolved_style.font_size,
            inverted=is_inverted,
            multiline=multiline,
            line_h=advance if multiline else 0,
            text=content,
        )

    def draw_rect(
        self,
        coords: RectangleCoordinates,
        *,
        anchor: Anchor = _RECT_DEFAULT_ANCHOR,
        color: int = _RECT_DEFAULT_COLOR,
        filled: bool = False,
    ) -> DrawRect:
        """
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

        """
        anchor_point = coords.anchor_coordinates(anchor)
        self._reject_out_of_bounds(coords, anchor_point.x, anchor_point.y)

        x, y, w, h = coords.xywh()
        return DrawRect(x=x, y=y, w=w, h=h, color=color, filled=filled)

    @staticmethod
    def _resolve_line_height(line_height: int | None, font_size: int) -> int:
        """
        Resolve the per-line vertical advance for multiline stacking.

        Use the caller's ``line_height`` when supplied; otherwise fall back to the
        font's default :func:`whiskerframe.metrics.line_advance`. A non-positive
        explicit advance is rejected as inconsistent with the layout model.

        Args:
        - line_height (`int | None`): Explicit per-line advance in px, or `None` to use the default.
        - font_size (`int`): Font-size selector used to look up the default advance.

        Raises:
        - `ValueError`: If ``line_height`` is supplied and not positive.

        Returns:
        `int`: The resolved per-line vertical advance in pixels.

        """
        if line_height is None:
            return line_advance(font_size)
        if line_height <= 0:
            msg = f"line_height must be positive, got {line_height!r}."
            raise ValueError(msg)
        return line_height

    @staticmethod
    def _layout_text(text: str, *, multiline: bool, inverted: bool) -> str:
        r"""
        Lay out the text payload, reversing line order when inverted.

        For multiline text the lines (split on ``\n``) are reversed when
        ``inverted`` is set, matching the imagesmacker 7.0.0 ``inverted``
        semantics that flip the stacking order (Req 8.3). Single-line text is
        returned unchanged; the color swap is handled separately.

        Args:
        - text (`str`): Text to lay out; lines separated by ``\n`` when ``multiline``.
        - multiline (`bool`): Whether the text is laid out as stacked lines.
        - inverted (`bool`): Whether to reverse the line order.

        Returns:
        `str`: The laid-out text with lines reversed when multiline and inverted.

        """
        if not (multiline and inverted):
            return text
        return "\n".join(reversed(text.split("\n")))

    @staticmethod
    def _resolve_colors(style: TextStyle, *, inverted: bool) -> tuple[int, int]:
        """
        Resolve foreground and background colors, swapping them when inverted.

        When ``inverted`` is set the style's foreground and background are swapped,
        matching the imagesmacker 7.0.0 ``inverted`` semantics (Req 8.3);
        otherwise the style colors are returned unchanged.

        Args:
        - style (`TextStyle`): Text style supplying the foreground and background colors.
        - inverted (`bool`): Whether to swap foreground and background.

        Returns:
        `tuple[int, int]`: The resolved ``(foreground, background)`` RGB565 colors.

        """
        if inverted:
            return style.bg_color, style.color
        return style.color, style.bg_color

    @staticmethod
    def _reject_out_of_bounds(coords: RectangleCoordinates, x: int, y: int) -> None:
        """
        Reject a resolved anchor point that falls outside the rectangle bounds.

        The imagesmacker 7.0.0 anchor model always resolves an anchor to a point
        on the target rectangle's bounding box. A point outside that box signals
        an inconsistent placement, so the command is rejected rather than
        approximated (Req 3.5).

        Args:
        - coords (`RectangleCoordinates`): Target rectangle whose bounds are checked.
        - x (`int`): Resolved anchor x pixel.
        - y (`int`): Resolved anchor y pixel.

        Raises:
        - `ValueError`: If ``(x, y)`` falls outside the ``coords`` bounding box.

        Returns:
        `None`: This check returns nothing when the placement is valid.

        """
        x1, y1, x2, y2 = coords.xyxy()
        if not (x1 <= x <= x2 and y1 <= y <= y2):
            msg = (
                f"Resolved placement ({x}, {y}) is outside the target rectangle "
                f"bounds ({x1}, {y1}, {x2}, {y2}); inconsistent with the "
                "imagesmacker 7.0.0 model."
            )
            raise ValueError(msg)
