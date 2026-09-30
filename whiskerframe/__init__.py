"""
whiskerframe: pure command builder for the CYD Display Link.

Expose the public host-side drawing API: rectangle coordinate types, the anchor
type, command models, the :class:`CommandBuilder`, and the wire
:func:`serialize` function. Importing this package pulls in only the pure command
path; the optional Pillow-based ``preview`` renderer and the pyserial
``transport`` are not imported here, so ``whiskerframe`` stays importable without
either optional dependency installed.
"""

from __future__ import annotations

from whiskerframe.anchors import Anchor
from whiskerframe.builder import CommandBuilder
from whiskerframe.coordinates import XYWH, XYXY, FourXY
from whiskerframe.models import DrawRect, DrawText, TextStyle
from whiskerframe.protocol import serialize

__all__ = [
    "XYWH",
    "XYXY",
    "Anchor",
    "CommandBuilder",
    "DrawRect",
    "DrawText",
    "FourXY",
    "TextStyle",
    "serialize",
]
