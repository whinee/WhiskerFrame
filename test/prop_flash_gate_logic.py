"""
Flash-gate permit/block property test for the irreversible-flash safety gate.

**Property 8: No flash write without a validated backup, explicit size, and confirmation**
**Validates: Requirements 7.2, 7.4, 7.5, 7.6**

For any combination of gate inputs, `scripts.flash_gate.gate_decision` permits an
irreversible write if and only if ALL three preconditions hold simultaneously:

1. a validated `Flash_Backup` is present (the `BackupValidation` argument is not
   `None` and its ``valid`` is `True`) (Req 7.4, 7.6);
2. an explicit flash size is supplied as a positive `int` that is not a `bool`
   (``None``, ``0``, negatives, and `bool` all count as unspecified/invalid)
   (Req 7.2); and
3. the operator explicitly confirmed the write (Req 7.5).

Any other combination MUST block. The property drives Hypothesis across the full
cross product of backup states (absent, present-but-invalid, present-and-valid),
explicit sizes (including ``None``, ``0``, negatives, `bool`, and valid positives),
and the confirmation flag, then compares ``gate_decision(...).permitted`` against
an independent oracle built from the same three conditions.

The script is pure (no esptool, no flash access), runs as
``uv run python test/prop_flash_gate_logic.py``, prints ``PASS`` on success, and
exits non-zero on the first failed assertion.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from flash_gate import (
    EXPECTED_FLASH_SIZE,
    BackupValidation,
    BlockReason,
    gate_decision,
)

# Backup states: None (no backup), an invalid validation, and a valid one.
_INVALID_BACKUP = BackupValidation(
    path=Path("backup.bin"),
    expected_size=EXPECTED_FLASH_SIZE,
    valid=False,
    exists=True,
    actual_size=1,
    reason="truncated",
)
_VALID_BACKUP = BackupValidation(
    path=Path("backup.bin"),
    expected_size=EXPECTED_FLASH_SIZE,
    valid=True,
    exists=True,
    actual_size=EXPECTED_FLASH_SIZE,
    reason=None,
)

backup_strategy = st.sampled_from((None, _INVALID_BACKUP, _VALID_BACKUP))

# Explicit sizes: unspecified/invalid values alongside valid positive integers.
# ``True``/``False`` cover the bool-is-not-a-size case (Req 7.2).
size_strategy = st.one_of(
    st.none(),
    st.booleans(),
    st.sampled_from((0, -1, -EXPECTED_FLASH_SIZE)),
    st.integers(min_value=1, max_value=EXPECTED_FLASH_SIZE),
)


def size_is_valid(explicit_size: object) -> bool:
    """
    Return the oracle for an acceptable explicit flash size.

    Args:
    - explicit_size (`object`): The candidate explicit size to classify.

    Returns:
    `bool`: `True` iff ``explicit_size`` is a positive, non-`bool` `int`.

    """
    return (
        isinstance(explicit_size, int)
        and not isinstance(explicit_size, bool)
        and explicit_size > 0
    )


@settings(max_examples=500)
@given(
    backup=backup_strategy,
    explicit_size=size_strategy,
    user_confirmed=st.booleans(),
)
def test_gate_permits_iff_all_preconditions_hold(
    backup: BackupValidation | None,
    explicit_size: int | None,
    user_confirmed: bool,
) -> None:
    """
    Assert ``permitted`` holds iff backup, size, and confirmation are all valid.

    Args:
    - backup (`BackupValidation | None`): Backup validation state under test.
    - explicit_size (`int | None`): Explicit flash size supplied to the gate.
    - user_confirmed (`bool`): Whether the operator confirmed the write.

    Raises:
    - `AssertionError`: If ``gate_decision(...).permitted`` disagrees with the
      independent oracle, or the block reasons are inconsistent with it.

    Returns:
    `None`: This property check returns nothing when the example holds.

    """
    backup_ok = backup is not None and backup.valid
    size_ok = size_is_valid(explicit_size)
    expected_permitted = backup_ok and size_ok and user_confirmed

    decision = gate_decision(backup, explicit_size, user_confirmed)

    assert decision.permitted is expected_permitted, (
        f"backup_ok={backup_ok} size_ok={size_ok} confirmed={user_confirmed}: "
        f"permitted={decision.permitted}, expected {expected_permitted}"
    )

    if expected_permitted:
        assert decision.reasons == (), "permitted decision must carry no reasons"
    else:
        assert decision.reasons, "blocked decision must carry at least one reason"
        assert (BlockReason.MISSING_BACKUP in decision.reasons) is not backup_ok
        assert (BlockReason.NO_EXPLICIT_SIZE in decision.reasons) is not size_ok
        assert (BlockReason.NOT_CONFIRMED in decision.reasons) is not user_confirmed


def main() -> None:
    """
    Run the flash-gate permit/block property and report success.

    Raises:
    - `AssertionError`: If any generated example fails.

    Returns:
    `None`: This entry point returns nothing.

    """
    test_gate_permits_iff_all_preconditions_hold()
    print("PASS")


if __name__ == "__main__":
    main()
