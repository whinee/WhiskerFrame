#!/usr/bin/env python3
"""
Generate goodbye splash artifacts for cyberdeck shutdown and reboot hooks.

Composites `assets/images/cess/lyra-doodle-transparent.png` over the theme background
(#191a28 / 0x18C5) with thickened strokes and "bai baiii" (shutdown) or "brb" (reboot).
Emits 128x128 big-endian RGB565 blobs and visual preview PNGs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_SOURCE_IMAGE: Path = _REPO_ROOT / "assets/images/cess/lyra-doodle-transparent.png"
_OUTPUT_DIR: Path = _REPO_ROOT / "assets/images"

_CANVAS_SIZE: int = 128
_THEME_BG: tuple[int, int, int] = (25, 26, 40)  # #191a28 / RGB565 0x18C5
_TEXT_COLOR: tuple[int, int, int] = (255, 179, 230)  # theme pink #ffb3e6


def _pack_rgb565_be(red: int, green: int, blue: int) -> bytes:
    """Pack 8-bit RGB into big-endian RGB565 bytes (matches DRAW_IMAGE blit)."""
    value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
    return bytes(((value >> 8) & 0xFF, value & 0xFF))


def generate_variant(text: str, output_prefix: str) -> tuple[Path, Path]:
    """Generate both preview PNG and .rgb565 blob for a goodbye variant."""
    if not _SOURCE_IMAGE.exists():
        raise FileNotFoundError(f"Source doodle not found: {_SOURCE_IMAGE}")

    src = Image.open(_SOURCE_IMAGE).convert("RGBA")

    # 1. Thicken strokes before downscaling: dilate alpha and color channels
    # The strokes are delicate; dilating preserves line weight during downsampling
    alpha = src.getchannel("A")
    thickened_alpha = alpha.filter(ImageFilter.MaxFilter(5))
    src.putalpha(thickened_alpha)

    # 2. Downscale doodle to fit within upper ~96x96 area of 128x128 canvas
    doodle_size = 96
    doodle_thumb = src.resize((doodle_size, doodle_size), Image.Resampling.LANCZOS)

    # 3. Create 128x128 canvas filled with theme background
    canvas = Image.new("RGBA", (_CANVAS_SIZE, _CANVAS_SIZE), (*_THEME_BG, 255))

    # Center doodle horizontally, offset slightly towards top
    doodle_x = (_CANVAS_SIZE - doodle_size) // 2
    doodle_y = 6
    canvas.alpha_composite(doodle_thumb, (doodle_x, doodle_y))

    # 4. Render subtitle text ("bai baiii" or "brb")
    draw = ImageDraw.Draw(canvas)
    # Use default font or load a clean bitmap font
    font = ImageFont.load_default()

    # Calculate text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (_CANVAS_SIZE - text_w) // 2
    text_y = _CANVAS_SIZE - 20

    # Draw text with subtle shadow for contrast
    draw.text((text_x + 1, text_y + 1), text, fill=(0, 0, 0, 180), font=font)
    draw.text((text_x, text_y), text, fill=(*_TEXT_COLOR, 255), font=font)

    # 5. Output Preview PNG (RGB)
    rgb_image = canvas.convert("RGB")
    preview_path = _OUTPUT_DIR / f"{output_prefix}-preview.png"
    rgb_image.save(preview_path, format="PNG")

    # 6. Output Big-Endian RGB565 Blob
    rgb565_path = _OUTPUT_DIR / f"{output_prefix}.rgb565"
    rgb565_bytes = bytearray()
    for y in range(_CANVAS_SIZE):
        for x in range(_CANVAS_SIZE):
            r, g, b = rgb_image.getpixel((x, y))
            rgb565_bytes.extend(_pack_rgb565_be(r, g, b))

    rgb565_path.write_bytes(rgb565_bytes)
    return preview_path, rgb565_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Cyberdeck goodbye splash artifacts")
    parser.parse_args()

    print("Generating shutdown splash ('bai baiii!')...")
    prev_sh, bin_sh = generate_variant("bai baiii!", "goodbye-shutdown")
    print(f"  Preview: {prev_sh}")
    print(f"  RGB565:  {bin_sh} ({bin_sh.stat().st_size} bytes)")

    print("Generating reboot splash ('brb :3')...")
    prev_rb, bin_rb = generate_variant("brb :3", "goodbye-reboot")
    print(f"  Preview: {prev_rb}")
    print(f"  RGB565:  {bin_rb} ({bin_rb.stat().st_size} bytes)")

    expected_size = _CANVAS_SIZE * _CANVAS_SIZE * 2
    assert bin_sh.stat().st_size == expected_size
    assert bin_rb.stat().st_size == expected_size
    print(f"SUCCESS: Both blobs verified at {expected_size} bytes (~32 KB).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
