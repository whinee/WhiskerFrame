"""
Pure flash-backup validation for the irreversible-flash safety gate (Req 7).

Flashing the CYD is irreversible: a write overwrites the factory firmware. Before
any write, the workflow reads the full flash into a `Flash_Backup` with an explicit
size of ``0x400000`` (4 MiB) using esptool (that read is a manual operator step).
This module holds only the *pure* validation logic that decides whether such a
backup file is trustworthy enough to gate the irreversible write.

A backup is valid if and only if the file exists AND its on-disk size equals the
expected flash size ``0x400000`` (and is therefore non-zero) (Req 7.3). Validation
is strict: a missing file, a partial/truncated read, a zero-size file, or an
oversized file all fail. There is no esptool invocation and no flash access here;
`validate_backup` only reads the candidate file's metadata (existence and size).
The actual esptool read is the manual task 19.1, and the write-permit decision that
consumes this result is the pure `gate_decision` function in this module.

`gate_decision` is the safety-critical chokepoint for the irreversible write: it
permits a write if and only if a validated backup exists, an explicit valid flash
size was supplied, and the operator explicitly confirmed the write (Req 7.2, 7.4,
7.5, 7.6). It is pure — no esptool, no flash access, no side effects — and defaults
to BLOCK. Its permit/block boolean is authoritative; the accompanying diagnostics
explain a block but never relax it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from debug import tracepoint

__all__ = [
    "EXPECTED_FLASH_SIZE",
    "BackupValidation",
    "BlockReason",
    "GateDecision",
    "gate_decision",
    "validate_backup",
]

EXPECTED_FLASH_SIZE: int = 0x400000
"""Expected full-flash backup size in bytes (4 MiB), per the explicit CYD flash size."""


@dataclass(frozen=True)
class BackupValidation:
    """
    Immutable result of validating a candidate flash-backup file.

    Produced by `validate_backup`. ``valid`` is the single authoritative gate
    signal: it is `True` only when the file exists and its size exactly matches
    the expected flash size. ``exists``, ``actual_size``, and ``reason`` are
    diagnostic detail explaining a failure and MUST NOT be used to relax the gate.

    Attributes:
    - path (`Path`): The candidate backup path that was checked.
    - expected_size (`int`): Required exact size in bytes for the backup to be valid.
    - valid (`bool`): `True` iff the file exists and its size equals ``expected_size``.
    - exists (`bool`): `True` iff the path exists and is a regular file.
    - actual_size (`int | None`): On-disk size in bytes, or `None` when the file is absent.
    - reason (`str | None`): Human-readable failure explanation, or `None` when valid.

    """

    path: Path
    expected_size: int
    valid: bool
    exists: bool
    actual_size: int | None
    reason: str | None


def validate_backup(
    path: str | Path,
    expected_size: int = EXPECTED_FLASH_SIZE,
) -> BackupValidation:
    """
    Validate a flash-backup file against the exact expected flash size.

    This is the hard precondition gating every irreversible flash write: the
    result is `valid` if and only if the file exists as a regular file AND its
    size equals ``expected_size`` exactly (and is therefore non-zero) (Req 7.3).
    The check is deliberately strict — partial, truncated, zero-size, or oversized
    files are all rejected — so a corrupt backup can never authorize a write. No
    esptool is invoked and no flash is accessed; only the candidate file's
    existence and size are read.

    Args:
    - path (`str | Path`): Path to the candidate backup file to validate.
    - expected_size (`int`, optional): Required exact size in bytes. Defaults to `EXPECTED_FLASH_SIZE`.

    Raises:
    - `ValueError`: If ``expected_size`` is not a positive integer, since an
      unspecified, zero, or negative size can never be a valid flash size (Req 7.2).

    Returns:
    `BackupValidation`: The validation result; check its ``valid`` attribute.

    """
    if expected_size <= 0:
        msg = (
            f"expected_size must be a positive flash size in bytes, "
            f"got {expected_size!r}"
        )
        raise ValueError(msg)

    candidate = Path(path)
    exists = candidate.is_file()
    actual_size = candidate.stat().st_size if exists else None

    if not exists:
        valid, reason = False, f"backup file does not exist: {candidate}"
    elif actual_size != expected_size:
        valid = False
        reason = (
            f"backup size {actual_size} bytes does not match expected "
            f"{expected_size} bytes"
        )
    else:
        valid, reason = True, None

    tracepoint(
        "flash.validate",
        path=candidate,
        valid=valid,
        actual_size=actual_size,
        reason=reason if reason is not None else "ok",
    )
    return BackupValidation(
        path=candidate,
        expected_size=expected_size,
        valid=valid,
        exists=exists,
        actual_size=actual_size,
        reason=reason,
    )


class BlockReason(Enum):
    """
    Enumerated reason a `gate_decision` blocked an irreversible flash write.

    Each member names one unmet precondition of the flash safety gate. A blocked
    decision may carry several reasons at once; a permitted decision carries none.
    These values are diagnostic only and never relax the authoritative permit
    boolean.

    Attributes:
    - MISSING_BACKUP: No validated `Flash_Backup` exists (Req 7.4, 7.6).
    - NO_EXPLICIT_SIZE: The operation supplied no explicit, valid flash size (Req 7.2).
    - NOT_CONFIRMED: The operator did not explicitly confirm the write (Req 7.5).

    """

    MISSING_BACKUP = "no validated flash backup exists"
    NO_EXPLICIT_SIZE = "no explicit valid flash size was specified"
    NOT_CONFIRMED = "operator did not explicitly confirm the write"


@dataclass(frozen=True)
class GateDecision:
    """
    Immutable permit/block decision for an irreversible CYD flash write.

    Produced by `gate_decision`. ``permitted`` is the single authoritative signal:
    it is `True` only when every safety precondition is met, and it defaults to
    `False` (BLOCK) whenever any precondition is unmet or unknown. ``reasons`` and
    ``detail`` explain a block for the operator but MUST NOT be used to override or
    relax ``permitted``; a caller must gate the write solely on ``permitted``.

    Attributes:
    - permitted (`bool`): `True` iff the write is authorized; defaults to blocking.
    - reasons (`tuple[BlockReason, ...]`): Unmet preconditions; empty iff permitted.
    - explicit_size (`int | None`): The explicit flash size supplied, or `None`.
    - backup_valid (`bool`): Whether a validated backup was present.
    - user_confirmed (`bool`): Whether the operator explicitly confirmed.
    - detail (`str`): Human-readable summary of the decision.

    """

    permitted: bool
    reasons: tuple[BlockReason, ...] = field(default_factory=tuple)
    explicit_size: int | None = None
    backup_valid: bool = False
    user_confirmed: bool = False
    detail: str = ""


def gate_decision(
    backup_validation: BackupValidation | None,
    explicit_size: int | None,
    user_confirmed: bool,
) -> GateDecision:
    """
    Decide whether an irreversible CYD flash write may proceed.

    This is the safety-critical chokepoint gating an irreversible hardware write
    (Req 7.2, 7.4, 7.5, 7.6). The write is permitted if and only if ALL of the
    following hold: a validated `Flash_Backup` exists (``backup_validation`` is not
    `None` and its ``valid`` is `True`), an explicit positive integer flash size was
    supplied (e.g. ``0x400000``), and the operator explicitly confirmed the write.
    Any other state — a missing or invalid backup, an unspecified/``ALL``/zero/
    negative/non-integer size, or an unconfirmed write — BLOCKS. The function is
    pure: it invokes no esptool, accesses no flash, and has no side effects, so the
    decision is deterministic and unit-testable without hardware.

    The returned ``permitted`` boolean is authoritative and defaults to blocking;
    the accompanying ``reasons`` and ``detail`` explain a block but never relax it.

    Args:
    - backup_validation (`BackupValidation | None`): Result from `validate_backup`,
      or `None` when no backup has been validated.
    - explicit_size (`int | None`): The explicit flash size in bytes for the
      operation. Must be a positive `int`; `None`, `bool`, `0`, or a negative value
      is treated as unspecified/invalid and blocks (Req 7.2).
    - user_confirmed (`bool`): `True` only if the operator explicitly confirmed the
      irreversible write (Req 7.5).

    Returns:
    `GateDecision`: The decision; gate the write solely on its ``permitted`` field.

    """
    reasons: list[BlockReason] = []

    backup_valid = backup_validation is not None and backup_validation.valid
    if not backup_valid:
        reasons.append(BlockReason.MISSING_BACKUP)

    # A bool is an int subclass but is never a valid flash size; reject it
    # alongside None, non-int, zero, and negative values.
    size_valid = (
        isinstance(explicit_size, int)
        and not isinstance(explicit_size, bool)
        and explicit_size > 0
    )
    if not size_valid:
        reasons.append(BlockReason.NO_EXPLICIT_SIZE)

    if not user_confirmed:
        reasons.append(BlockReason.NOT_CONFIRMED)

    permitted = not reasons
    if permitted:
        detail = (
            f"write permitted: validated backup present, explicit flash size "
            f"{explicit_size} bytes, operator confirmed"
        )
    else:
        detail = "write blocked: " + "; ".join(reason.value for reason in reasons)

    tracepoint(
        "flash.gate",
        permitted=permitted,
        reasons=",".join(reason.name for reason in reasons) or "none",
    )
    return GateDecision(
        permitted=permitted,
        reasons=tuple(reasons),
        explicit_size=explicit_size if size_valid else None,
        backup_valid=backup_valid,
        user_confirmed=user_confirmed,
        detail=detail,
    )
