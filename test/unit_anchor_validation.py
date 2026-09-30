"""
Unit tests for anchor validation (Req 3.4).

Exercise ``whiskerframe.anchors.validate_anchor`` against the imagesmacker 7.0.0
``[lmr][tmb]`` grammar: all nine valid anchors are accepted and returned
unchanged, the default argument resolves to ``"mm"``, and malformed strings
(wrong length or an invalid horizontal/vertical key) raise ``ValueError``.

The script is pure (no hardware, no Pillow), runs as
``uv run python test/unit_anchor_validation.py``, prints ``PASS`` on success, and
exits non-zero on the first failed check.
"""

from __future__ import annotations

import sys

from whiskerframe.anchors import DEFAULT_ANCHOR, validate_anchor

VALID_ANCHORS: tuple[str, ...] = (
    "lt",
    "mt",
    "rt",
    "lm",
    "mm",
    "rm",
    "lb",
    "mb",
    "rb",
)

INVALID_ANCHORS: tuple[str, ...] = (
    "",  # empty
    "m",  # too short
    "mmm",  # too long
    "xm",  # bad horizontal key
    "mx",  # bad vertical key
    "tm",  # keys transposed (t is not a horizontal key)
    "MM",  # wrong case
    "12",  # digits
    " m",  # leading space
)


def check_valid_accepted() -> None:
    """
    Assert every valid anchor is accepted and returned unchanged.

    Raises:
    - `AssertionError`: If a valid anchor is rejected or altered.

    Returns:
    `None`: This check returns nothing on success.

    """
    for anchor in VALID_ANCHORS:
        result = validate_anchor(anchor)
        assert result == anchor, f"valid {anchor!r} returned {result!r}"


def check_default_is_mm() -> None:
    """
    Assert the default argument resolves to the center anchor ``"mm"``.

    Raises:
    - `AssertionError`: If the default anchor is not ``"mm"``.

    Returns:
    `None`: This check returns nothing on success.

    """
    assert DEFAULT_ANCHOR == "mm", f"DEFAULT_ANCHOR is {DEFAULT_ANCHOR!r}"
    assert validate_anchor() == "mm", "validate_anchor() default is not 'mm'"


def check_invalid_rejected() -> None:
    """
    Assert every malformed anchor raises ``ValueError``.

    Raises:
    - `AssertionError`: If a malformed anchor is accepted instead of rejected.

    Returns:
    `None`: This check returns nothing on success.

    """
    for anchor in INVALID_ANCHORS:
        try:
            validate_anchor(anchor)
        except ValueError:
            continue
        msg = f"invalid {anchor!r} was accepted"
        raise AssertionError(msg)


def main() -> None:
    """
    Run all anchor-validation checks and report success.

    Raises:
    - `AssertionError`: If any check fails.

    Returns:
    `None`: This entry point returns nothing.

    """
    check_valid_accepted()
    check_default_is_mm()
    check_invalid_rejected()
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
