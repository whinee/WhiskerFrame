r"""
PC-side splash converter: image -> letterboxed 320x240 little-endian RGB565 blob.

Convert the configured boot-splash image (``terminal.splash.image`` in
``.whiskerframe.yaml``) into the raw pixel blob the Pi daemon streams to the CYD
without ever running an imaging library on the deck. The image is resized to fit
the 320x240 panel preserving aspect ratio, letterboxed onto a black canvas, and
emitted as little-endian RGB565 (two bytes per pixel, high byte last) to match the
firmware ``DRAW_IMAGE`` pixel contract. A full frame is ``320 * 240 * 2 =
153600`` bytes.

This script runs only on the programmer workstation (it imports Pillow, the
``preview`` extra); the Pi reads the ready ``.rgb565`` artifact via
``pi/terminal/splash.py``. It is idempotent: re-running regenerates the same bytes
for the same input, and it writes the output path configured in
``terminal.splash.rgb565``. Invoke it through the ``just splash`` recipe.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from config import PROJECT_ROOT, load_yaml_config

if TYPE_CHECKING:
    from PIL import Image as ImageModule

__all__ = [
    "PANEL_HEIGHT",
    "PANEL_WIDTH",
    "convert_image_to_rgb565",
    "main",
    "resolve_splash_paths",
]

PANEL_WIDTH: int = 320
"""Target splash width in pixels (CYD landscape panel width)."""

PANEL_HEIGHT: int = 240
"""Target splash height in pixels (CYD landscape panel height)."""

_RGB565_BYTES: int = PANEL_WIDTH * PANEL_HEIGHT * 2
"""Expected size of a full-frame RGB565 blob (two bytes per pixel)."""


def _pack_rgb565_le(red: int, green: int, blue: int) -> bytes:
    """
    Pack one 8-bit RGB triple into a little-endian RGB565 pixel.

    Quantize the channels to 5/6/5 bits, combine them into a 16-bit value, and
    emit it low byte first to match the firmware's little-endian pixel reads.

    Args:
    - red (`int`): Red channel in ``[0, 255]``.
    - green (`int`): Green channel in ``[0, 255]``.
    - blue (`int`): Blue channel in ``[0, 255]``.

    Returns:
    `bytes`: The two little-endian RGB565 bytes for the pixel.

    """
    value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
    return bytes((value & 0xFF, (value >> 8) & 0xFF))


def _letterbox(image: ImageModule.Image) -> ImageModule.Image:
    """
    Resize an image to fit 320x240 preserving aspect ratio, on a black canvas.

    Scale the image down (or up) so it fits entirely within the panel while
    keeping its aspect ratio, then centre it on an opaque black 320x240 canvas so
    the output is always exactly panel-sized.

    Args:
    - image (`ImageModule.Image`): The source image (any mode/size).

    Returns:
    `ImageModule.Image`: An ``RGB`` image of exactly ``320x240`` pixels.

    """
    from PIL import Image

    source = image.convert("RGB")
    source.thumbnail((PANEL_WIDTH, PANEL_HEIGHT), Image.LANCZOS)
    canvas = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), (0, 0, 0))
    offset_x = (PANEL_WIDTH - source.width) // 2
    offset_y = (PANEL_HEIGHT - source.height) // 2
    canvas.paste(source, (offset_x, offset_y))
    return canvas


def convert_image_to_rgb565(image_path: Path) -> bytes:
    """
    Convert an image file into a letterboxed 320x240 little-endian RGB565 blob.

    Open the image, letterbox it onto the panel, and pack every pixel into
    little-endian RGB565. The result is always exactly ``153600`` bytes.

    Args:
    - image_path (`Path`): Path to the source image file.

    Raises:
    - `FileNotFoundError`: If ``image_path`` does not exist.

    Returns:
    `bytes`: The ``320 * 240 * 2`` little-endian RGB565 bytes.

    """
    from PIL import Image

    if not image_path.is_file():
        msg = f"splash source image not found: {image_path}"
        raise FileNotFoundError(msg)
    with Image.open(image_path) as handle:
        canvas = _letterbox(handle)
    pixels = canvas.load()
    out = bytearray()
    for y in range(PANEL_HEIGHT):
        for x in range(PANEL_WIDTH):
            red, green, blue = pixels[x, y]  # type: ignore[index, misc]
            out += _pack_rgb565_le(red, green, blue)
    return bytes(out)


def resolve_splash_paths() -> tuple[Path, Path]:
    """
    Resolve the splash source image and output blob paths from config.

    Read ``terminal.splash.image`` and ``terminal.splash.rgb565`` from
    ``.whiskerframe.yaml`` (falling back to the example config), resolving both
    relative to the project root.

    Raises:
    - `KeyError`: If either splash path key is missing from the configuration.

    Returns:
    `tuple[Path, Path]`: The ``(source_image, output_rgb565)`` absolute paths.

    """
    config = load_yaml_config()
    terminal = config.get("terminal", {}) if isinstance(config, dict) else {}
    splash = terminal.get("splash", {}) if isinstance(terminal, dict) else {}
    image = splash.get("image")
    rgb565 = splash.get("rgb565")
    if not image or not rgb565:
        msg = "terminal.splash.image and terminal.splash.rgb565 must be configured."
        raise KeyError(msg)
    return (PROJECT_ROOT / str(image), PROJECT_ROOT / str(rgb565))


def main() -> int:
    """
    Convert the configured splash image and write the ``.rgb565`` artifact.

    Resolve the configured paths, convert the source image to the panel-sized
    little-endian RGB565 blob, and write it to the configured output path,
    reporting the byte count. Idempotent: the same input yields the same output.

    Returns:
    `int`: Process exit code (``0`` on success).

    """
    source, output = resolve_splash_paths()
    blob = convert_image_to_rgb565(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(blob)
    print(f"splash: {source.name} -> {output} ({len(blob)} bytes)", flush=True)
    if len(blob) != _RGB565_BYTES:
        print(
            f"WARNING: expected {_RGB565_BYTES} bytes, wrote {len(blob)}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
