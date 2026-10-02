"""
CYD terminal bridge: host-side pure core for a real terminal on the CYD panel.

Render a real ``bash`` login shell onto the CYD's ILI9341 panel, typed on the
M5Stack CardKB, over the existing ``whiskerframe`` serial command path. This
package holds the pure, hardware-free pieces (unit/property testable on the host
without any device, Pillow, or PAM import):

- `grid`: a character `Grid` with a cursor, scrolling, and a `diff` that
  coalesces changed cells into draw runs.
- `theme`: the config-driven piiiiink RGB565 palette and a total SGR-to-RGB565
  map.
- `vt`: a VT100-subset emulator turning shell output bytes into grid mutations.
- `login`: a masked-entry login state machine plus a guarded PAM auth adapter.

The I/O-bound glue (PTY, serial, CardKB, systemd) lives in sibling modules that
are built on top of this pure core.
"""

from __future__ import annotations

__all__ = [
    "__version__",
]

__version__ = "0.1.0"
