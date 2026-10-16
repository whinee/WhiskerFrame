#!/usr/bin/env python3
"""
Reproducible visual verification tool for the WhiskerFrame CYD Display Link.

Inspects display observability, renders resolved drawing commands (DrawText, DrawRect,
DrawCells) to PNG images using the preview renderer and Pillow, and generates text grid
dumps representing the terminal screen state.

Usage:
    uv run python scripts/visual_verify.py [--output-dir DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from whiskerframe.builder import CommandBuilder
from whiskerframe.coordinates import XYWH
from whiskerframe.preview import PreviewRenderer
from whiskerframe.terminal import TerminalGeometry
from terminal.grid import Grid


def verify_visual_pipeline(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}

    # 1. Render sample CommandBuilder drawing commands (DrawText & DrawRect)
    builder = CommandBuilder()
    screen_rect = XYWH(0, 0, 320, 240)
    box_rect = XYWH(10, 10, 300, 220)

    builder.draw_rect(screen_rect, color=0x18C5, filled=True)  # Background
    builder.draw_rect(box_rect, color=0x50DC, filled=False)  # Border
    builder.draw_text(
        screen_rect,
        text="WHISKERFRAME CYBERDECK\nVisual Verification Active\nDisplay: ILI9341 320x240",
        anchor="mt",
        style=None,
        multiline=True,
        inverted=False,
    )
    builder.draw_text(
        box_rect,
        text="[OK] Framebuffer Bypass Verified\n[OK] Serial Command Pipeline Active\n[OK] Multi-Geometry Typography Ready",
        anchor="lt",
        multiline=True,
    )

    renderer = PreviewRenderer(width=320, height=240, background=0x0000)
    image = renderer.render(builder.commands)
    png_path = output_dir / "visual_verify_render.png"
    image.save(png_path)
    results["render_png"] = png_path

    # 2. Render text grid state (DrawCells / VT grid)
    geom = TerminalGeometry.for_font_size(1)  # 53x30
    grid = Grid(cols=geom.cols, rows=geom.rows, default_fg=0xFD9C, default_bg=0x18C5)

    # Draw welcome banner on grid
    welcome_text = "CYBERDECK TERMINAL GRID SIMULATION"
    for i, ch in enumerate(welcome_text):
        if i < geom.cols:
            grid.set_cursor(2, 2 + i)
            grid.put_char(ch, 0xFF6E, 0x18C5)

    status_text = "WS1:bash  BAT:88% (4.12V)  CPU:42C  MEM:128MB"
    for i, ch in enumerate(status_text):
        if i < geom.cols:
            grid.set_cursor(0, i)
            grid.put_char(ch, 0x50DC, 0x191A)

    grid_lines: list[str] = []
    for r in range(grid.rows):
        row_chars = []
        for c in range(grid.cols):
            cell = grid.cell_at(r, c)
            row_chars.append(cell.char)
        grid_lines.append("".join(row_chars))

    txt_path = output_dir / "visual_verify_grid.txt"
    txt_path.write_text("\n".join(grid_lines), encoding="utf-8")
    results["grid_txt"] = txt_path

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproducible visual verification tool for Whiskerframe")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "dev" / "specimens",
        help="Directory to save verification output artifacts",
    )
    args = parser.parse_args()

    print("Running WhiskerFrame visual verification pipeline...")
    paths = verify_visual_pipeline(args.output_dir)
    for name, path in paths.items():
        print(f"  - Generated {name}: {path}")
    print("Visual verification completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
