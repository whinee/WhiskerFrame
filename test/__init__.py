"""
Runnable test scripts for the whiskerframe pure command path (Req 9).

Each module in this package is a standalone script exercising the pure
`Command_Builder` and wire protocol with no hardware and no Pillow. The scripts
are run directly (``python test/<name>.py``) by the justfile ``test`` recipe and
exit non-zero on the first failed assertion. This ``__init__.py`` marks ``test``
as a package so it satisfies the ruff ``INP001`` implicit-namespace check that
applies to the ``test`` directory.
"""

from __future__ import annotations
