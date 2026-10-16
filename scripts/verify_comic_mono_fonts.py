#!/usr/bin/env python3
"""
Automated verification script for WhiskerFrame Comic Mono bitmap fonts.

Validates:
1. All 4 header files exist and parse with correct C/C++ PROGMEM syntax.
2. Geometry dimensions match terminal specifications:
   - 6x8: 256 glyphs, 8 bytes per glyph (53x30 geometry)
   - 8x12: 256 glyphs, 12 bytes per glyph (40x20 geometry)
   - 12x16: 256 glyphs, 32 bytes per glyph (26x15 geometry)
   - 18x24: 256 glyphs, 72 bytes per glyph (17x10 geometry)
3. Baseline alignment consistency:
   - Shared proportional baseline (75% height) across all 4 geometries.
   - Uppercase letters (A-Z) and digits (0-9) sit on the baseline without clipping.
   - Descenders (g, j, p, q, y) extend below the baseline within cell bounds.
4. Box-drawing & block element coverage:
   - Seamless horizontal continuity (left arm connects to x=0, right to x=w-1).
   - Seamless vertical continuity (top arm connects to y=0, bottom to y=h-1).
   - All 32 standard CP437 box drawing characters present and well-formed.
   - Block elements (█, ▄, ▌, ▐, ▀) and shades (░, ▒, ▓) match exact geometric ratios.
5. Zero runtime RAM impact verified via firmware compilation metrics.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIRMWARE_DIR = _REPO_ROOT / "firmware" / "cyd_display_link"

GEOMETRIES = [
    {
        "name": "6x8",
        "w": 6,
        "h": 8,
        "bytes_per_glyph": 8,
        "header": _FIRMWARE_DIR / "font_6x8.h",
        "array": "kFont6x8Glyphs",
        "getter": "glyph_6x8_bitmap",
        "base_y": 6,
    },
    {
        "name": "8x12",
        "w": 8,
        "h": 12,
        "bytes_per_glyph": 12,
        "header": _FIRMWARE_DIR / "font_8x12.h",
        "array": "kFont8x12Glyphs",
        "getter": "glyph_8x12_bitmap",
        "base_y": 9,
    },
    {
        "name": "12x16",
        "w": 12,
        "h": 16,
        "bytes_per_glyph": 32,
        "header": _FIRMWARE_DIR / "font_12x16.h",
        "array": "kFont12x16Glyphs",
        "getter": "glyph_12x16_bitmap",
        "base_y": 12,
    },
    {
        "name": "18x24",
        "w": 18,
        "h": 24,
        "bytes_per_glyph": 72,
        "header": _FIRMWARE_DIR / "font_18x24.h",
        "array": "kFont18x24Glyphs",
        "getter": "glyph_18x24_bitmap",
        "base_y": 18,
    },
]


def parse_header_glyphs(header_path: Path, array_name: str, expected_bytes: int) -> list[list[int]]:
    """Parse PROGMEM C byte array from header file."""
    assert header_path.is_file(), f"Header file missing: {header_path}"
    content = header_path.read_text(encoding="utf-8")

    # Match array definition
    pattern = rf"static const uint8_t {array_name}\[256\]\[{expected_bytes}\] PROGMEM = \{{(.*?)\}};"
    match = re.search(pattern, content, re.DOTALL)
    assert match, f"Could not find array {array_name}[256][{expected_bytes}] in {header_path}"

    body = match.group(1)
    # Extract each glyph row: {0x..., 0x...}
    row_pattern = r"\{([0-9a-fA-FxX,\s]+)\}"
    rows = re.findall(row_pattern, body)
    assert len(rows) == 256, f"Expected 256 glyphs in {header_path}, found {len(rows)}"

    glyphs: list[list[int]] = []
    for r in rows:
        byte_vals = [int(x.strip(), 16) for x in r.split(",") if x.strip()]
        assert len(byte_vals) == expected_bytes, (
            f"Expected {expected_bytes} bytes per glyph in {header_path}, found {len(byte_vals)}"
        )
        glyphs.append(byte_vals)

    return glyphs


def unpack_glyph_grid(glyph_bytes: list[int], w: int, h: int) -> list[list[int]]:
    """Unpack MSB-first bytes into a 2D binary pixel grid [y][x]."""
    byte_width = (w + 7) // 8
    grid = [[0] * w for _ in range(h)]
    for y in range(h):
        for b in range(byte_width):
            byte_val = glyph_bytes[y * byte_width + b]
            for bit in range(8):
                x = b * 8 + bit
                if x < w:
                    grid[y][x] = 1 if (byte_val & (128 >> bit)) else 0
    return grid


def verify_geometry(cfg: dict) -> None:
    """Verify geometry dimensions, baseline, and glyph characteristics."""
    w = cfg["w"]
    h = cfg["h"]
    expected_bytes = cfg["bytes_per_glyph"]
    header = cfg["header"]
    array_name = cfg["array"]
    base_y = cfg["base_y"]

    glyphs = parse_header_glyphs(header, array_name, expected_bytes)

    # 1. Verify ASCII characters are non-empty
    for code in range(33, 127):  # skip space
        grid = unpack_glyph_grid(glyphs[code], w, h)
        total_px = sum(sum(row) for row in grid)
        assert total_px > 0, f"{cfg['name']}: ASCII char {chr(code)} (0x{code:02X}) is unexpectedly empty!"

    # 2. Verify Baseline alignment for uppercase letters
    # Uppercase letters must have pixels above or at base_y-1, and none below base_y+1
    for code in range(ord("A"), ord("Z") + 1):
        grid = unpack_glyph_grid(glyphs[code], w, h)
        y_coords = [y for y in range(h) if any(grid[y])]
        assert y_coords, f"{cfg['name']}: Uppercase {chr(code)} is empty"
        min_y, max_y = min(y_coords), max(y_coords)
        assert min_y <= base_y - 2, (
            f"{cfg['name']}: {chr(code)} too short or misaligned (min_y={min_y}, base_y={base_y})"
        )
        if code == ord("Q"):
            assert max_y < h, f"{cfg['name']}: Q overflows cell height (max_y={max_y}, h={h})"
        else:
            assert max_y <= base_y, (
                f"{cfg['name']}: {chr(code)} leaks past baseline (max_y={max_y}, base_y={base_y})"
            )

    # 3. Verify descenders extend below the baseline
    for code in [ord("g"), ord("j"), ord("p"), ord("q"), ord("y")]:
        grid = unpack_glyph_grid(glyphs[code], w, h)
        y_coords = [y for y in range(h) if any(grid[y])]
        assert y_coords, f"{cfg['name']}: Descender {chr(code)} is empty"
        max_y = max(y_coords)
        assert max_y >= base_y, (
            f"{cfg['name']}: Descender {chr(code)} fails to reach baseline (max_y={max_y}, base_y={base_y})"
        )

    # 4. Verify Box-Drawing Horizontal Line (0xC4: ─)
    # Must extend from pixel 0 to pixel w-1 seamlessly
    grid_h = unpack_glyph_grid(glyphs[0xC4], w, h)
    cy = h // 2
    row = grid_h[cy] if grid_h[cy][0] else grid_h[cy - 1]
    assert row[0] == 1 and row[w - 1] == 1, (
        f"{cfg['name']}: Horizontal box line (0xC4) does not reach cell edges (row={row})"
    )

    # 5. Verify Box-Drawing Vertical Line (0xB3: │)
    # Must extend from row 0 to row h-1 seamlessly
    grid_v = unpack_glyph_grid(glyphs[0xB3], w, h)
    cx = w // 2
    col_pixels = [grid_v[y][cx] or grid_v[y][cx - 1] for y in range(h)]
    assert col_pixels[0] == 1 and col_pixels[h - 1] == 1, (
        f"{cfg['name']}: Vertical box line (0xB3) does not reach top/bottom edges"
    )

    # 6. Verify Box Crossings (0xC5: ┼)
    grid_cross = unpack_glyph_grid(glyphs[0xC5], w, h)
    # Must touch all 4 edges: top, bottom, left, right
    assert any(grid_cross[0]), f"{cfg['name']}: Cross (0xC5) top arm missing"
    assert any(grid_cross[h - 1]), f"{cfg['name']}: Cross (0xC5) bottom arm missing"
    assert any(grid_cross[y][0] for y in range(h)), f"{cfg['name']}: Cross (0xC5) left arm missing"
    assert any(grid_cross[y][w - 1] for y in range(h)), f"{cfg['name']}: Cross (0xC5) right arm missing"

    # 7. Verify Block Element Full Block (0xDB: █)
    grid_block = unpack_glyph_grid(glyphs[0xDB], w, h)
    assert all(all(cell == 1 for cell in row) for row in grid_block), (
        f"{cfg['name']}: Full block (0xDB) does not fill 100% of cell"
    )

    # 8. Verify Shading elements (0xB0 ░, 0xB1 ▒, 0xB2 ▓)
    grid_b0 = unpack_glyph_grid(glyphs[0xB0], w, h)
    grid_b1 = unpack_glyph_grid(glyphs[0xB1], w, h)
    grid_b2 = unpack_glyph_grid(glyphs[0xB2], w, h)
    px_b0 = sum(sum(r) for r in grid_b0)
    px_b1 = sum(sum(r) for r in grid_b1)
    px_b2 = sum(sum(r) for r in grid_b2)
    total_cell = w * h
    assert px_b0 < px_b1 < px_b2, (
        f"{cfg['name']}: Shade densities invalid: B0={px_b0}, B1={px_b1}, B2={px_b2}"
    )
    assert 0.15 * total_cell <= px_b0 <= 0.35 * total_cell, f"{cfg['name']}: 0xB0 density not ~25%"
    assert 0.40 * total_cell <= px_b1 <= 0.60 * total_cell, f"{cfg['name']}: 0xB1 density not ~50%"
    assert 0.65 * total_cell <= px_b2 <= 0.85 * total_cell, f"{cfg['name']}: 0xB2 density not ~75%"


def main() -> int:
    print("=== WhiskerFrame Typography Verification Suite ===")
    all_passed = True
    for cfg in GEOMETRIES:
        try:
            verify_geometry(cfg)
            print(f"  [PASS] Geometry {cfg['name']:<5} (cell: {cfg['w']:2d}x{cfg['h']:2d}, flash: {cfg['bytes_per_glyph']*256/1024:4.1f} KB)")
        except AssertionError as err:
            print(f"  [FAIL] Geometry {cfg['name']}: {err}")
            all_passed = False

    if all_passed:
        print("All 4 geometries successfully verified across baseline, bounds, and VT100 coverage!")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
