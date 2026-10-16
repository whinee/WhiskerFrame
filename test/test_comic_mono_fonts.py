"""
Pytest integration tests for WhiskerFrame Comic Mono bitmap fonts.

Validates the 4 generated font headers, geometry dimensions, baseline consistency,
and VT100 / box-drawing glyph coverage.
"""

from __future__ import annotations

import pytest

from scripts.verify_comic_mono_fonts import GEOMETRIES, verify_geometry


@pytest.mark.parametrize("cfg", GEOMETRIES, ids=[cfg["name"] for cfg in GEOMETRIES])
def test_font_geometry_and_coverage(cfg: dict) -> None:
    """Verify font header dimensions, baseline alignment, and box-drawing coverage."""
    verify_geometry(cfg)
