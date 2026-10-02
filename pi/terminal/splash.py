r"""
Boot-splash blit: stream a pre-converted RGB565 blob to the CYD (no Pillow).

Read the ready ``.rgb565`` artifact produced on the programmer by
``scripts/convert_splash.py`` and push it to the firmware as a sequence of
``DRAW_IMAGE`` commands, two panel rows per chunk. The Pi never runs an imaging
library: it only reads the raw bytes and frames them, so this module is
stdlib-plus-``whiskerframe`` only.

A full splash is ``320 * 240 * 2 = 153600`` bytes. Each chunk covers ``320 * 2``
pixels (a ``1280``-byte payload), comfortably under the firmware frame cap, so a
whole splash is 120 small frames. The blob is little-endian RGB565 to match the
firmware ``DRAW_IMAGE`` pixel contract.

Field-robustness: a missing, empty, or short/truncated blob is skipped silently
(the login screen is the safe idle state), and any serial write error is caught
so a splash never crashes or blocks the daemon's boot path.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from whiskerframe.protocol import serialize
from whiskerframe.terminal import DISPLAY_HEIGHT, DISPLAY_WIDTH, DrawImage

from .debug import tracepoint

if TYPE_CHECKING:
    from os import PathLike

__all__ = [
    "CHUNK_ROWS",
    "SPLASH_BYTES",
    "SplashSink",
    "show_splash",
]

CHUNK_ROWS: int = 2
"""Panel rows carried per ``DRAW_IMAGE`` chunk (``320 * 2`` px -> 1280-byte payload)."""

_BYTES_PER_PIXEL: int = 2
"""RGB565 is two bytes per pixel."""

SPLASH_BYTES: int = DISPLAY_WIDTH * DISPLAY_HEIGHT * _BYTES_PER_PIXEL
"""Expected size of a full-frame splash blob (``320 * 240 * 2`` = 153600)."""

_CHUNK_PAYLOAD: int = DISPLAY_WIDTH * CHUNK_ROWS * _BYTES_PER_PIXEL
"""Bytes of pixel data in one full chunk (``320 * 2 * 2`` = 1280)."""


class SplashSink(Protocol):
    """
    Minimal transport protocol: anything that can send framed bytes.

    Satisfied by :class:`whiskerframe.transport.SerialTransport` and by test
    doubles, so the splash blit can be exercised without real serial hardware.
    """

    def send(self, frame: bytes) -> None:
        """
        Send one framed byte sequence to the display.

        Args:
        - frame (`bytes`): A complete framed drawing command.

        Returns:
        `None`: The frame is transmitted.

        """
        ...


def _read_blob(rgb565_path: Path) -> bytes | None:
    """
    Read the splash blob, returning ``None`` when it is unusable.

    Treat a missing file, a read error, an empty file, or a blob that is not a
    whole number of panel rows as "no usable splash" so the caller skips the
    splash gracefully rather than crashing.

    Args:
    - rgb565_path (`Path`): Path to the pre-converted ``.rgb565`` blob.

    Returns:
    `bytes | None`: The blob bytes, or ``None`` if missing/empty/misaligned.

    """
    try:
        blob = rgb565_path.read_bytes()
    except OSError:
        return None
    row_bytes = DISPLAY_WIDTH * _BYTES_PER_PIXEL
    if not blob or len(blob) % row_bytes != 0:
        return None
    return blob


def show_splash(transport: SplashSink, rgb565_path: str | PathLike[str]) -> None:
    """
    Blit a pre-converted RGB565 splash blob to the CYD over serial.

    Read the little-endian RGB565 blob at ``rgb565_path`` and stream it to the
    firmware as ``DRAW_IMAGE`` chunks of :data:`CHUNK_ROWS` rows each (clamped so
    a short final chunk only covers the rows actually present). A missing, empty,
    or row-misaligned blob is skipped silently, and a serial write error aborts
    the splash without raising, so this is always safe on the boot path.

    Args:
    - transport (`SplashSink`): The serial transport (or compatible sink).
    - rgb565_path (`str | PathLike[str]`): Path to the ``.rgb565`` blob.

    Returns:
    `None`: The splash is sent best-effort; failures are swallowed.

    """
    blob = _read_blob(Path(rgb565_path))
    if blob is None:
        tracepoint("terminal.splash", status="skipped", path=str(rgb565_path))
        return
    row_bytes = DISPLAY_WIDTH * _BYTES_PER_PIXEL
    total_rows = len(blob) // row_bytes
    sent = 0
    try:
        for top in range(0, total_rows, CHUNK_ROWS):
            rows = min(CHUNK_ROWS, total_rows - top)
            start = top * row_bytes
            data = blob[start : start + rows * row_bytes]
            command = DrawImage(x=0, y=top, w=DISPLAY_WIDTH, h=rows, data=data)
            transport.send(serialize(command))
            sent += 1
    except OSError as err:
        tracepoint("terminal.splash", status="write_error", chunk=sent, error=err)
        return
    tracepoint("terminal.splash", status="shown", chunks=sent, rows=total_rows)
