r"""
Env-gated, stdlib-only tracepoint helper for the Pi CYD-terminal daemon.

Mirror of ``pi/battery_monitor/debug.py`` for the ``terminal`` package so the
terminal bridge can emit the same named, greppable "test points" as the rest of
the Pi tooling. This module MUST stay stdlib-only: the uv-managed Pi venv ships
only ``pydantic`` / ``pyserial`` / ``pyyaml`` / ``simplepam``, so the daemon's
debug path may not pull in any external dependency.

Tracepoints are gated on the ``WHISKERFRAME_DEBUG`` environment variable: when it
is truthy the helper prints a single structured line per tracepoint to
``stderr`` (which systemd journald captures); when it is unset (the default)
every tracepoint is a near-zero-cost no-op.

Emitted lines use a stable, greppable grammar so ``grep '\[TP\]'`` over a journal
finds them::

    [TP] <name> key=value key2=value2

The terminal daemon uses the ``terminal.*`` namespace: ``terminal.splash``,
``terminal.login``, ``terminal.auth`` (which NEVER logs the password),
``terminal.shell_start``, ``terminal.logout``, ``terminal.keyframe``,
``terminal.serial_reopen``, and ``terminal.resize``.

Tracepoints never raise: a value that fails to format is rendered as
``<unrepr>`` rather than crashing the daemon, so instrumentation can never take
down the bridge loop. Keep this module in sync with
``pi/battery_monitor/debug.py`` (identical API: `DEBUG_ENV`, `is_debug`,
`tracepoint`) when changing the tracepoint contract.
"""

from __future__ import annotations

import os
import sys
from typing import Any

__all__ = [
    "DEBUG_ENV",
    "is_debug",
    "tracepoint",
]

DEBUG_ENV: str = "WHISKERFRAME_DEBUG"
"""Environment variable that gates tracepoint emission (truthy enables)."""

# Values (lower-cased) that count as "truthy" for DEBUG_ENV.
_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes"})


def is_debug() -> bool:
    r"""
    Report whether tracepoint emission is enabled.

    Read `DEBUG_ENV` from the process environment and treat ``1``, ``true``, or
    ``yes`` (case-insensitive, surrounding whitespace ignored) as enabled. Any
    other value, or an unset variable, is disabled.

    Returns:
    `bool`: `True` when tracepoints should emit, `False` otherwise.

    """
    return os.environ.get(DEBUG_ENV, "").strip().lower() in _TRUTHY


def _format_field(value: Any) -> str:
    r"""
    Render a single tracepoint field value, never raising.

    Convert ``value`` to its string form. If ``str`` raises (a broken
    ``__str__``), fall back to ``<unrepr>`` so a formatting failure can never
    propagate out of a tracepoint.

    Args:
    - value (`Any`): The field value to render.

    Returns:
    `str`: The rendered value, or ``<unrepr>`` when rendering fails.

    """
    try:
        return str(value)
    except Exception:  # noqa: BLE001 - a bad __str__ must not crash the caller
        return "<unrepr>"


def tracepoint(name: str, /, **fields: Any) -> None:
    r"""
    Emit a single structured tracepoint line to ``stderr`` when debug is enabled.

    When `is_debug` is `True`, print ``[TP] <name> key=value ...`` to ``stderr``
    with the fields in the order supplied. When debug is disabled this returns
    immediately without formatting anything, so an instrumented hot path pays
    only a cheap environment-variable check. The function never raises: any error
    while formatting a field or writing the line is swallowed, so instrumentation
    can never crash the daemon.

    Use dotted, greppable names like ``terminal.action`` (e.g. ``terminal.auth``)
    so related tracepoints share a prefix. ``name`` is positional-only, so a field
    may itself be called ``name``. NEVER pass a plaintext password as a field.

    Args:
    - name (`str`): Dotted tracepoint name, e.g. ``"terminal.shell_start"``.
    - fields (`Any`): Arbitrary keyword fields rendered as ``key=value`` pairs.

    Returns:
    `None`: This function returns nothing.

    """
    if not is_debug():
        return
    try:
        parts = [f"{key}={_format_field(value)}" for key, value in fields.items()]
        line = " ".join(("[TP]", name, *parts)) if parts else f"[TP] {name}"
        print(line, file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001, S110 - a tracepoint must never crash the caller
        pass
