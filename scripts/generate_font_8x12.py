#!/usr/bin/env python3
"""
Generate firmware/cyd_display_link/font_8x12.h.

Renders 95 printable ASCII glyphs (32 to 126) from DejaVu Sans Mono into
an 8x12 bitmapped cell for the intermediate 40x20 terminal geometry.
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

_REPO_ROOT = Path(__file__).resolve().parent.parent
_HEADER_PATH = _REPO_ROOT / "firmware/cyd_display_link/font_8x12.h"


def generate_font_header() -> None:
    font_path = "/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf"
    if not Path(font_path).exists():
        raise FileNotFoundError(f"Font not found: {font_path}")

    font = ImageFont.truetype(font_path, 12)

    lines: list[str] = [
        "// Auto-generated 8x12 bitmap font for intermediate 40x20 terminal geometry.",
        "// Each character is 12 rows of 8 bits (1 byte per row). ASCII 32 to 126.",
        "#pragma once",
        "#include <stdint.h>",
        "#include <pgmspace.h>",
        "",
        "static const uint8_t kFont8x12Glyphs[95][12] PROGMEM = {",
    ]

    for code in range(32, 127):
        ch = chr(code)
        im = Image.new("1", (8, 12), 0)
        draw = ImageDraw.Draw(im)
        draw.text((0, -2), ch, font=font, fill=1)

        row_hex: list[str] = []
        for y in range(12):
            byte = 0
            for x in range(8):
                if im.getpixel((x, y)):
                    byte |= 1 << (7 - x)
            row_hex.append(f"0x{byte:02X}")

        if ch == "\\":
            comment = "// 0x5C '\\\\'"
        elif ch == "'":
            comment = "// 0x27 '\\''"
        else:
            comment = f"// 0x{code:02X} '{ch}'"

        lines.append(f"    {{{', '.join(row_hex)}}},  {comment}")

    lines.extend([
        "};",
        "",
        "inline const uint8_t* glyph_8x12_bitmap(char ch) {",
        "  uint8_t c = static_cast<uint8_t>(ch);",
        "  if (c < 32 || c > 126) c = 32;",
        "  return kFont8x12Glyphs[c - 32];",
        "}",
        "",
    ])

    _HEADER_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {_HEADER_PATH} ({_HEADER_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    generate_font_header()
