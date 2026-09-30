r"""
Example: build and serialize a multiline ``DRAW_TEXT`` command (Req 10.3).

Use :class:`whiskerframe.CommandBuilder` to lay out three ``\n``-separated lines
anchored at the top-left (``"lt"``) of a 200x120 region, stacking lines by the
font's default line advance. Both an upright variant and an ``inverted=True``
variant are built, serialized with :func:`whiskerframe.serialize`, and printed --
inversion reverses the line order and swaps foreground/background, matching the
imagesmacker 7.0.0 ``inverted`` semantics. Pure command path -- no Pillow, no
serial port.

Run it with ``python examples/03_multiline_text.py`` (or ``just examples``).
"""

from __future__ import annotations

from whiskerframe import XYWH, CommandBuilder, TextStyle, serialize
from whiskerframe.models import DrawText

_LINES = "Line one\nLine two\nLine three"


def build_multiline(*, inverted: bool) -> DrawText:
    """
    Build a top-left-anchored multiline ``DRAW_TEXT`` command.

    Anchor three stacked lines at the top-left of a 200x120 region using an amber
    foreground on a navy background, optionally inverting line order and colors.

    Args:
    - inverted (`bool`): Whether to reverse line order and swap foreground/background.

    Returns:
    `DrawText`: The resolved multiline text command.

    """
    builder = CommandBuilder()
    region = XYWH(x=0, y=0, w=200, h=120)
    style = TextStyle(color=0xFD20, bg_color=0x0010, font_size=2)  # amber on navy
    return builder.draw_text(
        region,
        _LINES,
        anchor="lt",
        style=style,
        multiline=True,
        inverted=inverted,
    )


def show_command(label: str, command: DrawText) -> None:
    """
    Print a labelled multiline command and its serialized frame.

    Args:
    - label (`str`): Human-readable label for the variant.
    - command (`DrawText`): Resolved multiline text command to display.

    Returns:
    `None`: This function only prints.

    """
    frame = serialize(command)
    print(f"== {label} ==")
    print(f"  text (payload order) = {command.text!r}")
    print(f"  origin    = ({command.x}, {command.y})")
    print(f"  line_h    = {command.line_h}")
    print(f"  color     = {command.color:#06x}")
    print(f"  bg_color  = {command.bg_color:#06x}")
    print(f"  inverted  = {command.inverted}")
    print(f"  frame ({len(frame)} bytes) = {frame.hex(' ')}\n")


def main() -> None:
    """
    Build, serialize, and print upright and inverted multiline commands.

    Returns:
    `None`: This function only prints.

    """
    show_command("Multiline DRAW_TEXT (upright)", build_multiline(inverted=False))
    show_command("Multiline DRAW_TEXT (inverted)", build_multiline(inverted=True))


if __name__ == "__main__":
    main()
