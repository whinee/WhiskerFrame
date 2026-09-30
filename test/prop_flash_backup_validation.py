"""
Flash-backup validation property test for the irreversible-flash safety gate.

**Property 7: Flash-backup validation accepts only the exact flash size**
**Validates: Requirements 7.3**

For any candidate backup file, `scripts.flash_gate.validate_backup` reports
``valid`` as `True` if and only if the file exists as a regular file AND its
on-disk size equals the expected flash size ``0x400000`` (4 MiB, and therefore
non-zero). Every other case -- a missing path, a zero-byte file, an off-by-one
truncated or oversized file, or any other mismatched size -- MUST fail.

The property is exercised by materializing a real temporary file of a
Hypothesis-generated size (including ``0x400000`` exactly plus boundary sizes
such as zero, off-by-one, and larger) and comparing ``validate_backup(path).valid``
against the independent oracle ``size == EXPECTED_FLASH_SIZE``. A missing-file
case is checked separately. Every temporary file is deleted after each example.

The script is pure (no esptool, no flash access), runs as
``uv run python test/prop_flash_backup_validation.py``, prints ``PASS`` on
success, and exits non-zero on the first failed assertion.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from flash_gate import EXPECTED_FLASH_SIZE, validate_backup

# Sizes that must be covered on top of Hypothesis' random draws: the exact
# expected size, its off-by-one neighbours, zero, and a clearly oversized file.
BOUNDARY_SIZES: tuple[int, ...] = (
    0,
    1,
    EXPECTED_FLASH_SIZE - 1,
    EXPECTED_FLASH_SIZE,
    EXPECTED_FLASH_SIZE + 1,
    EXPECTED_FLASH_SIZE * 2,
)

# Keep generated sizes near the expected size so temp files stay small while
# still hitting the exact match, off-by-one, zero, and oversized cases.
size_strategy = st.one_of(
    st.sampled_from(BOUNDARY_SIZES),
    st.integers(min_value=0, max_value=EXPECTED_FLASH_SIZE + 16),
)


def write_sized_file(directory: Path, size: int) -> Path:
    """
    Create a regular file of exactly ``size`` bytes inside ``directory``.

    Uses a sparse truncate so even a 4 MiB file costs no real disk space.

    Args:
    - directory (`Path`): Directory that will hold the temporary file.
    - size (`int`): Exact number of bytes the file must report on disk.

    Returns:
    `Path`: Path to the newly created file.

    """
    path = directory / "backup.bin"
    with path.open("wb") as handle:
        handle.truncate(size)
    return path


@settings(max_examples=200)
@given(size=size_strategy)
def test_validation_matches_exact_size_oracle(size: int) -> None:
    """
    Assert ``valid`` holds iff an existing file's size equals ``0x400000``.

    Args:
    - size (`int`): On-disk size in bytes for the materialized backup file.

    Raises:
    - `AssertionError`: If ``validate_backup(...).valid`` disagrees with the
      independent oracle ``size == EXPECTED_FLASH_SIZE``.

    Returns:
    `None`: This property check returns nothing when the example holds.

    """
    with tempfile.TemporaryDirectory() as tmp:
        path = write_sized_file(Path(tmp), size)
        result = validate_backup(path)

    expected_valid = size == EXPECTED_FLASH_SIZE
    assert (
        result.valid is expected_valid
    ), f"size {size}: valid={result.valid}, expected {expected_valid}"
    assert result.exists is True, f"size {size}: exists should be True"
    if expected_valid:
        assert result.actual_size == EXPECTED_FLASH_SIZE
        assert result.reason is None
    else:
        assert result.reason is not None


def test_missing_file_is_invalid() -> None:
    """
    Assert a non-existent path is never valid.

    Raises:
    - `AssertionError`: If a missing path is reported valid or existing.

    Returns:
    `None`: This check returns nothing when the missing path fails validation.

    """
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "does-not-exist.bin"
        result = validate_backup(missing)

    assert result.valid is False, "missing file must not be valid"
    assert result.exists is False, "missing file must not report existence"
    assert result.actual_size is None
    assert result.reason is not None


def main() -> None:
    """
    Run the flash-backup validation property and report success.

    Raises:
    - `AssertionError`: If any generated example or the missing-file case fails.

    Returns:
    `None`: This entry point returns nothing.

    """
    test_missing_file_is_invalid()
    test_validation_matches_exact_size_oracle()
    print("PASS")


if __name__ == "__main__":
    main()
