"""
Example: build and serialize a single ``DRAW_TEXT`` command (Req 10.2).

Use :class:`whiskerframe.CommandBuilder` to anchor a single line of text at the
center (``"mm"``) of a 200x80 region, then serialize the resolved
:class:`whiskerframe.DrawText` into the length-prefixed wire frame with
:func:`whiskerframe.serialize`. The resolved command fields and the framed bytes
(as hex) are printed so the payload layout is visible. Pure command path -- no
Pillow, no serial port.

Run it with ``python examples/02_text.py`` (or ``just examples``).
"""

from __future__ import annotations

from whiskerframe import XYWH, CommandBuilder, TextStyle, serialize
from whiskerframe.models import DrawText


def build_text() -> DrawText:
    """
    Build a center-anchored single-line ``DRAW_TEXT`` command.

    Anchor the text ``"Meow"`` at the center of a 200x80 region using a
    cyan foreground, and let the builder resolve the anchor to a pixel.

    Returns:
    `DrawText`: The resolved single-line text command.

    """
    builder = CommandBuilder()
    region = XYWH(x=0, y=0, w=200, h=80)
    style = TextStyle(color=0x07FF, font_size=2)  # cyan (RGB565), size 2
    return builder.draw_text(region, "Meow", anchor="mm", style=style)


def show_command(command: DrawText) -> None:
    """
    Print the resolved command fields and the serialized frame.

    Args:
    - command (`DrawText`): Resolved text command to display and serialize.

    Returns:
    `None`: This function only prints.

    """
    frame = serialize(command)
    print("== Resolved DRAW_TEXT command ==")
    print(f"  text      = {command.text!r}")
    print(f"  anchor    = {command.anchor!r}")
    print(f"  origin    = ({command.x}, {command.y})")
    print(f"  color     = {command.color:#06x}")
    print(f"  bg_color  = {command.bg_color:#06x}")
    print(f"  font_size = {command.font_size}")
    print(f"  inverted  = {command.inverted}")
    print(f"  multiline = {command.multiline}")

    print("\n== Serialized frame ==")
    print(f"  length = {len(frame)} bytes")
    print(f"  hex    = {frame.hex(' ')}")


def main() -> None:
    """
    Build, serialize, and print a single ``DRAW_TEXT`` command.

    Returns:
    `None`: This function only prints.

    """
    show_command(build_text())


if __name__ == "__main__":
    main()
