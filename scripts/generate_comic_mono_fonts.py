#!/usr/bin/env python3
"""
Generate multi-geometry Comic Mono bitmap font headers for CYD display link.

Compiles 256 CP437 glyphs for all 4 terminal geometries:
- 53x30 terminal geometry: 6x8 font (font_size=1)
- 40x20 terminal geometry: 8x12 font (font_size=5)
- 26x15 terminal geometry: 12x16 font (font_size=2)
- 17x10 terminal geometry: 18x24 font (font_size=3)

Features:
- Sourced from Comic Mono (https://github.com/dtinth/comic-mono-font).
- Strict typographic baseline alignment (proportional 75% baseline height).
- 100% VT100 / CP437 box-drawing and block element coverage via procedural
  rasterization ensuring seamless edge-to-edge cell tiling with zero gaps.
- Standard PROGMEM flash arrays consuming zero runtime SRAM on ESP32.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageDraw, ImageFont

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ASSETS_DIR = _REPO_ROOT / "assets" / "fonts"
_FIRMWARE_DIR = _REPO_ROOT / "firmware" / "cyd_display_link"

_COMIC_MONO_URL = (
    "https://raw.githubusercontent.com/dtinth/comic-mono-font/master/ComicMono.ttf"
)
_COMIC_MONO_SHA256 = (
    "3bc1425e922a16abf0ec767effe4d0268439b4c0dce98432e07d15f5dad57196"
)

# Standard fallback font paths for extended Latin/Greek symbols (CP437 0x80..0xFF)
_FALLBACK_FONT_CANDIDATES = [
    Path("/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSansMono.ttf"),
]


class FontGeometryConfig(NamedTuple):
    name: str
    width: int
    height: int
    pt_size: int
    baseline_y: int
    fallback_pt: int
    fallback_baseline_y: int
    header_filename: str
    array_name: str
    getter_name: str


GEOMETRIES: tuple[FontGeometryConfig, ...] = (
    FontGeometryConfig(
        name="6x8",
        width=6,
        height=8,
        pt_size=8,
        baseline_y=6,
        fallback_pt=7,
        fallback_baseline_y=6,
        header_filename="font_6x8.h",
        array_name="kFont6x8Glyphs",
        getter_name="glyph_6x8_bitmap",
    ),
    FontGeometryConfig(
        name="8x12",
        width=8,
        height=12,
        pt_size=11,
        baseline_y=9,
        fallback_pt=11,
        fallback_baseline_y=9,
        header_filename="font_8x12.h",
        array_name="kFont8x12Glyphs",
        getter_name="glyph_8x12_bitmap",
    ),
    FontGeometryConfig(
        name="12x16",
        width=12,
        height=16,
        pt_size=16,
        baseline_y=12,
        fallback_pt=15,
        fallback_baseline_y=12,
        header_filename="font_12x16.h",
        array_name="kFont12x16Glyphs",
        getter_name="glyph_12x16_bitmap",
    ),
    FontGeometryConfig(
        name="18x24",
        width=18,
        height=24,
        pt_size=24,
        baseline_y=18,
        fallback_pt=23,
        fallback_baseline_y=18,
        header_filename="font_18x24.h",
        array_name="kFont18x24Glyphs",
        getter_name="glyph_18x24_bitmap",
    ),
)

# CP437 box-drawing specifications: (up, down, left, right) arms
# 0 = none, 1 = single line, 2 = double line
BOX_DRAWING_SPECS: dict[int, tuple[int, int, int, int]] = {
    0xB3: (1, 1, 0, 0),  # │
    0xB4: (1, 1, 1, 0),  # ┤
    0xB5: (1, 1, 2, 0),  # ╡
    0xB6: (2, 2, 1, 0),  # ╢
    0xB7: (0, 2, 1, 0),  # ╖
    0xB8: (0, 1, 2, 0),  # ╕
    0xB9: (2, 2, 2, 0),  # ╣
    0xBA: (2, 2, 0, 0),  # ║
    0xBB: (0, 2, 2, 0),  # ╗
    0xBC: (2, 0, 2, 0),  # ╝
    0xBD: (2, 0, 1, 0),  # ╜
    0xBE: (1, 0, 2, 0),  # ╛
    0xBF: (0, 1, 1, 0),  # ┐
    0xC0: (1, 0, 0, 1),  # └
    0xC1: (1, 0, 1, 1),  # ┴
    0xC2: (0, 1, 1, 1),  # ┬
    0xC3: (1, 1, 0, 1),  # ├
    0xC4: (0, 0, 1, 1),  # ─
    0xC5: (1, 1, 1, 1),  # ┼
    0xC6: (1, 1, 0, 2),  # ╞
    0xC7: (2, 2, 0, 1),  # ╟
    0xC8: (2, 0, 0, 2),  # ╚
    0xC9: (0, 2, 0, 2),  # ╔
    0xCA: (2, 0, 2, 2),  # ╩
    0xCB: (0, 2, 2, 2),  # ╦
    0xCC: (2, 2, 0, 2),  # ╠
    0xCD: (0, 0, 2, 2),  # ═
    0xCE: (2, 2, 2, 2),  # ╬
    0xCF: (2, 0, 1, 1),  # ╧
    0xD0: (1, 0, 2, 2),  # ╨
    0xD1: (0, 1, 2, 2),  # ╤
    0xD2: (0, 2, 1, 1),  # ╥
    0xD3: (2, 0, 0, 1),  # ╙
    0xD4: (1, 0, 0, 2),  # ╘
    0xD5: (0, 1, 0, 2),  # ╒
    0xD6: (0, 2, 0, 1),  # ╓
    0xD7: (2, 2, 1, 1),  # ╫
    0xD8: (1, 1, 2, 2),  # ╪
    0xD9: (1, 0, 1, 0),  # ┘
    0xDA: (0, 1, 0, 1),  # ┌
}


def ensure_comic_mono_font() -> Path:
    """Ensure ComicMono.ttf is present and verify its SHA256 checksum."""
    candidates = [
        _ASSETS_DIR / "ComicMono.ttf",
        Path.home() / ".local" / "share" / "fonts" / "ComicMono.ttf",
    ]

    for path in candidates:
        if path.is_file():
            hasher = hashlib.sha256()
            hasher.update(path.read_bytes())
            if hasher.hexdigest() == _COMIC_MONO_SHA256:
                return path

    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    target = _ASSETS_DIR / "ComicMono.ttf"
    print(f"Downloading ComicMono.ttf from {_COMIC_MONO_URL}...")
    urllib.request.urlretrieve(_COMIC_MONO_URL, target)  # noqa: S310

    hasher = hashlib.sha256()
    hasher.update(target.read_bytes())
    digest = hasher.hexdigest()
    if digest != _COMIC_MONO_SHA256:
        raise ValueError(
            f"Checksum mismatch for ComicMono.ttf: expected {_COMIC_MONO_SHA256}, got {digest}"
        )
    return target


def find_fallback_font() -> Path | None:
    """Find a system fallback monospace font for extended CP437 glyphs."""
    for path in _FALLBACK_FONT_CANDIDATES:
        if path.is_file():
            return path
    return None


def render_procedural_box(
    w: int, h: int, up: int, down: int, left: int, right: int
) -> list[list[int]]:
    """Procedurally render a box-drawing glyph to guarantee edge-to-edge connectivity."""
    grid = [[0] * w for _ in range(h)]
    cx = w // 2
    cy = h // 2

    v_thick = 2 if w >= 18 else 1
    h_thick = 2 if h >= 24 else 1

    xs_single = [cx] if v_thick == 1 else [cx - 1, cx]
    ys_single = [cy] if h_thick == 1 else [cy - 1, cy]

    off_x = 1 if w <= 8 else (2 if w <= 14 else 3)
    off_y = 1 if h <= 10 else (2 if h <= 16 else 3)

    x_left = cx - off_x
    x_right = cx + off_x
    y_top = cy - off_y
    y_bot = cy + off_y

    # Single vertical
    if up == 1:
        for x in xs_single:
            for y in range(0, cy + 1):
                grid[y][x] = 1
    if down == 1:
        for x in xs_single:
            for y in range(cy, h):
                grid[y][x] = 1

    # Single horizontal
    if left == 1:
        for y in ys_single:
            for x in range(0, cx + 1):
                grid[y][x] = 1
    if right == 1:
        for y in ys_single:
            for x in range(cx, w):
                grid[y][x] = 1

    # Double vertical
    if up == 2:
        y_stop_l = (
            y_top
            if left == 2
            else (cy if left == 1 else (y_bot if right == 2 else cy))
        )
        y_stop_r = (
            y_top
            if right == 2
            else (cy if right == 1 else (y_bot if left == 2 else cy))
        )
        if down == 2:
            y_stop_l = h
            y_stop_r = h
        for y in range(0, y_stop_l):
            grid[y][x_left] = 1
        for y in range(0, y_stop_r):
            grid[y][x_right] = 1

    if down == 2:
        y_start_l = (
            y_bot
            if left == 2
            else (cy if left == 1 else (y_top if right == 2 else cy))
        )
        y_start_r = (
            y_bot
            if right == 2
            else (cy if right == 1 else (y_top if left == 2 else cy))
        )
        if up == 2:
            y_start_l = 0
            y_start_r = 0
        for y in range(y_start_l, h):
            grid[y][x_left] = 1
        for y in range(y_start_r, h):
            grid[y][x_right] = 1

    # Double horizontal
    if left == 2:
        x_stop_t = (
            x_left
            if up == 2
            else (cx if up == 1 else (x_right if down == 2 else cx))
        )
        x_stop_b = (
            x_left
            if down == 2
            else (cx if down == 1 else (x_right if up == 2 else cx))
        )
        if right == 2:
            x_stop_t = w
            x_stop_b = w
        for x in range(0, x_stop_t):
            grid[y_top][x] = 1
        for x in range(0, x_stop_b):
            grid[y_bot][x] = 1

    if right == 2:
        x_start_t = (
            x_right
            if up == 2
            else (cx if up == 1 else (x_left if down == 2 else cx))
        )
        x_start_b = (
            x_right
            if down == 2
            else (cx if down == 1 else (x_left if up == 2 else cx))
        )
        if left == 2:
            x_start_t = 0
            x_start_b = 0
        for x in range(x_start_t, w):
            grid[y_top][x] = 1
        for x in range(x_start_b, w):
            grid[y_bot][x] = 1

    # Mixed crossings
    if (left == 2 or right == 2) and up == 1:
        for x in xs_single:
            for y in range(0, y_top + 1):
                grid[y][x] = 1
    if (left == 2 or right == 2) and down == 1:
        for x in xs_single:
            for y in range(y_bot, h):
                grid[y][x] = 1
    if (up == 2 or down == 2) and left == 1:
        for y in ys_single:
            for x in range(0, x_left + 1):
                grid[y][x] = 1
    if (up == 2 or down == 2) and right == 1:
        for y in ys_single:
            for x in range(x_right, w):
                grid[y][x] = 1

    return grid


def render_procedural_block(w: int, h: int, code: int) -> list[list[int]]:
    """Procedurally render block and shading elements (0xB0..0xB2, 0xDB..0xDF, 0xFE)."""
    grid = [[0] * w for _ in range(h)]
    if code == 0xDB:  # Full block █
        return [[1] * w for _ in range(h)]
    if code == 0xDC:  # Lower half block ▄
        for y in range(h // 2, h):
            for x in range(w):
                grid[y][x] = 1
    elif code == 0xDD:  # Left half block ▌
        for y in range(h):
            for x in range(0, w // 2):
                grid[y][x] = 1
    elif code == 0xDE:  # Right half block ▐
        for y in range(h):
            for x in range(w // 2, w):
                grid[y][x] = 1
    elif code == 0xDF:  # Upper half block ▀
        for y in range(0, h // 2):
            for x in range(w):
                grid[y][x] = 1
    elif code == 0xB0:  # Light shade ░ (25% dither)
        for y in range(h):
            for x in range(w):
                if (x + y * 2) % 4 == 0:
                    grid[y][x] = 1
    elif code == 0xB1:  # Medium shade ▒ (50% checkerboard)
        for y in range(h):
            for x in range(w):
                if (x + y) % 2 == 0:
                    grid[y][x] = 1
    elif code == 0xB2:  # Dark shade ▓ (75% dither)
        for y in range(h):
            for x in range(w):
                if (x + y * 2) % 4 != 0:
                    grid[y][x] = 1
    elif code == 0xFE:  # ■ Centered square bullet
        qw = max(1, w // 4)
        qh = max(1, h // 4)
        for y in range(qh, h - qh):
            for x in range(qw, w - qw):
                grid[y][x] = 1
    return grid


def pack_bitmap_bytes(grid: list[list[int]], w: int, h: int) -> list[int]:
    """
    Pack pixel grid into MSB-first bytes matching TFT_eSPI::drawBitmap byteWidth layout.
    """
    byte_width = (w + 7) // 8
    result: list[int] = []
    for y in range(h):
        for b in range(byte_width):
            byte_val = 0
            for bit in range(8):
                x = b * 8 + bit
                if x < w and grid[y][x]:
                    byte_val |= 128 >> bit
            result.append(byte_val)
    return result


def render_glyph(
    code: int,
    cfg: FontGeometryConfig,
    comic_font: ImageFont.FreeTypeFont,
    fallback_font: ImageFont.FreeTypeFont | None,
) -> tuple[list[int], str]:
    """Render a single CP437 glyph into packed bytes and description string."""
    u_char = bytes([code]).decode("cp437")

    # 1. Procedural box-drawing
    if code in BOX_DRAWING_SPECS:
        u, d, l, r = BOX_DRAWING_SPECS[code]
        grid = render_procedural_box(cfg.width, cfg.height, u, d, l, r)
        return pack_bitmap_bytes(grid, cfg.width, cfg.height), f"U+{ord(u_char):04X} ({u_char}) [box]"

    # 2. Procedural block / shade elements
    if code in (0xB0, 0xB1, 0xB2, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF, 0xFE):
        grid = render_procedural_block(cfg.width, cfg.height, code)
        return pack_bitmap_bytes(grid, cfg.width, cfg.height), f"U+{ord(u_char):04X} ({u_char}) [block]"

    # 3. Printable ASCII from Comic Mono
    if 32 <= code <= 126:
        pad_y = 4
        im_big = Image.new("1", (cfg.width, cfg.height + pad_y * 2), 0)
        draw_big = ImageDraw.Draw(im_big)
        draw_big.text((0, cfg.baseline_y + pad_y), u_char, font=comic_font, fill=1, anchor="ls")
        bbox = im_big.getbbox()

        # If a glyph ascender overflows above the top edge (e.g. ^ or ` in 6x8),
        # clamp its top to row 0 so it stays fully visible.
        shift_y = 0
        if bbox and bbox[1] < pad_y:
            shift_y = pad_y - bbox[1]

        im = Image.new("1", (cfg.width, cfg.height), 0)
        im.paste(im_big.crop((0, pad_y - shift_y, cfg.width, pad_y - shift_y + cfg.height)))
        grid = [[im.getpixel((x, y)) for x in range(cfg.width)] for y in range(cfg.height)]
        if u_char == "\\":
            desc = "'\\\\'"
        elif u_char == "'":
            desc = "'\\''"
        else:
            desc = f"'{u_char}'"
        return pack_bitmap_bytes(grid, cfg.width, cfg.height), f"{desc} [ComicMono]"

    # 4. Extended symbols (0x80..0xAF, 0xE0..0xFD) via fallback font or blank
    if fallback_font is not None and code > 32 and code != 255:
        im = Image.new("1", (cfg.width, cfg.height), 0)
        draw = ImageDraw.Draw(im)
        draw.text((0, cfg.fallback_baseline_y), u_char, font=fallback_font, fill=1, anchor="ls")
        grid = [[im.getpixel((x, y)) for x in range(cfg.width)] for y in range(cfg.height)]
        return pack_bitmap_bytes(grid, cfg.width, cfg.height), f"U+{ord(u_char):04X} ({u_char}) [fallback]"

    # 5. Default/Control characters (0..31, 255): blank
    blank_grid = [[0] * cfg.width for _ in range(cfg.height)]
    return pack_bitmap_bytes(blank_grid, cfg.width, cfg.height), f"0x{code:02X} [blank]"


def generate_header_for_geometry(
    cfg: FontGeometryConfig,
    comic_path: Path,
    fallback_path: Path | None,
    output_dir: Path,
) -> Path:
    """Generate C/C++ header file for a specific geometry configuration."""
    comic_font = ImageFont.truetype(str(comic_path), cfg.pt_size)
    fallback_font = (
        ImageFont.truetype(str(fallback_path), cfg.fallback_pt)
        if fallback_path
        else None
    )

    bytes_per_row = (cfg.width + 7) // 8
    bytes_per_glyph = cfg.height * bytes_per_row

    out_path = output_dir / cfg.header_filename
    lines: list[str] = [
        f"// Auto-generated {cfg.width}x{cfg.height} Comic Mono bitmap font.",
        f"// Geometry: {cfg.name} (cell: {cfg.width}x{cfg.height} px, {bytes_per_glyph} bytes/glyph).",
        "// Coverage: 256 CP437 glyphs with procedural VT100 box-drawing & blocks.",
        "// Format: MSB-first packed rows compatible with TFT_eSPI::drawBitmap.",
        "#pragma once",
        "#include <stdint.h>",
        "#include <pgmspace.h>",
        "",
        f"static const uint8_t {cfg.array_name}[256][{bytes_per_glyph}] PROGMEM = {{",
    ]

    for code in range(256):
        byte_vals, desc = render_glyph(code, cfg, comic_font, fallback_font)
        hex_str = ", ".join(f"0x{b:02X}" for b in byte_vals)
        lines.append(f"    {{{hex_str}}},  // 0x{code:02X}: {desc}")

    lines.extend([
        "};",
        "",
        f"inline const uint8_t* {cfg.getter_name}(char ch) {{",
        "  uint8_t c = static_cast<uint8_t>(ch);",
        f"  return {cfg.array_name}[c];",
        "}",
        "",
    ])

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Comic Mono bitmap font headers for WhiskerFrame."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_FIRMWARE_DIR,
        help="Directory where header files will be generated.",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== WhiskerFrame Comic Mono Typography Pipeline ===")
    comic_path = ensure_comic_mono_font()
    print(f"Sourced Comic Mono: {comic_path}")

    fallback_path = find_fallback_font()
    if fallback_path:
        print(f"Sourced fallback font: {fallback_path}")
    else:
        print("Warning: No fallback monospace font found for extended symbols.")

    total_bytes = 0
    for cfg in GEOMETRIES:
        out_file = generate_header_for_geometry(
            cfg, comic_path, fallback_path, output_dir
        )
        size_kb = out_file.stat().st_size / 1024
        bytes_per_glyph = cfg.height * ((cfg.width + 7) // 8)
        flash_kb = (256 * bytes_per_glyph) / 1024
        total_bytes += 256 * bytes_per_glyph
        print(
            f"  Generated {cfg.name:<5} -> {out_file.name:<16} "
            f"({flash_kb:4.1f} KB flash, header {size_kb:5.1f} KB)"
        )

    print(
        f"Successfully generated all 4 font headers ({total_bytes / 1024:.1f} KB total flash)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
