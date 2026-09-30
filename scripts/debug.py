r"""
Env-gated, stdlib-only tracepoint helper for host-side tooling (``scripts/``).

Emit named, greppable "test points" from the host tooling so both humans and AI
agents can trace decision and I/O boundaries without a debugger. Tracepoints are
gated on the ``WHISKERFRAME_DEBUG`` environment variable: when it is truthy the
helper prints a single structured line per tracepoint to ``stderr``; when it is
unset (the default) every tracepoint is a near-zero-cost no-op.

Emitted lines use a stable, greppable grammar so ``grep '\[TP\]'`` over a log or
journal finds them::

    [TP] <name> key=value key2=value2

No timestamp is added -- journald and interactive terminals already timestamp
each line. Tracepoints never raise: a value that fails to format is rendered as
``<unrepr>`` rather than crashing the caller, so instrumentation can never take
down the host tooling. This module depends only on the Python standard library
so it stays importable from any script.

The Pi daemon carries a byte-for-byte mirror at ``pi/battery_monitor/debug.py``
(which must also stay stdlib-only); keep the two in sync when changing the API.
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
    can never crash the caller.

    Use dotted, greppable names like ``module.action`` (e.g. ``pi_env.ssh_run``)
    so related tracepoints share a prefix. ``name`` is positional-only, so a
    field may itself be called ``name`` (e.g. ``tracepoint("config.env",
    name=var)``).

    Args:
    - name (`str`): Dotted tracepoint name, e.g. ``"config.env"``.
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
