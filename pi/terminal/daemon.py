r"""
Entry point for the CYD terminal bridge: load config, run the bridge, log.

Resolve the ``terminal:`` (and ``cardkb:``) blocks of ``.whiskerframe.yaml`` via
``scripts/config.py`` into a :class:`.bridge.BridgeConfig` with fallbacks that
match the live-verified hardware, open the CardKB, and run the
:class:`.bridge.TerminalBridge` splash -> login -> shell loop over the keypad's
self-recovering key stream. Logging goes to stdout/stderr, which systemd's
journald captures (``journalctl -u terminal``).

Field-robustness: the bridge itself never crashes the loop (every I/O surface
reopens on error); this entry point only wires configuration and the CardKB
reader to it. The service unit runs ``Restart=always`` so an unforeseen fatal
error still brings the deck back to the login gate. The CardKB stream uses
``robust_keys`` so a transient I2C glitch self-recovers without input loss taking
down the daemon. No interactive prompts run in this path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from cardkb.reader import CardKB  # type: ignore[import-not-found]

from .bridge import BridgeConfig, TerminalBridge
from .debug import tracepoint
from .theme import load_theme

__all__ = [
    "load_bridge_config",
    "log",
    "main",
    "run",
]


def _load_yaml_config() -> dict[str, Any]:
    r"""
    Load ``.whiskerframe.yaml`` via ``scripts/config.py`` with a safe fallback.

    On the Pi, ``scripts/`` sits two levels up from ``pi/terminal/`` under the
    deploy root, so its parent is added to ``sys.path`` to reuse the project's
    ``load_yaml_config``. If the module or file is unavailable, an empty mapping
    is returned so the daemon falls back entirely to the verified defaults.

    Returns:
    `dict[str, Any]`: The parsed configuration mapping (empty on any failure).

    """
    scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from config import load_yaml_config  # type: ignore[import-not-found]
    except ImportError:
        return {}
    loaded = load_yaml_config()
    return loaded if isinstance(loaded, dict) else {}


def _as_int(value: Any, default: int) -> int:
    r"""
    Coerce a config value to ``int`` (accepting hex strings), else the default.

    Args:
    - value (`Any`): Raw config value (``int``, hex/decimal ``str``, or ``None``).
    - default (`int`): Value used when coercion fails.

    Returns:
    `int`: The coerced integer or the default.

    """
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return default
    return default


def _as_float(value: Any, default: float) -> float:
    r"""
    Coerce a config value to ``float``, falling back on any failure.

    Args:
    - value (`Any`): Raw config value.
    - default (`float`): Value used when coercion fails.

    Returns:
    `float`: The coerced float or the default.

    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_splash_path(terminal: dict[str, Any]) -> str:
    r"""
    Resolve the splash ``.rgb565`` path from the terminal config.

    Return an absolute path to the pre-converted splash blob when splash is
    enabled and configured, else an empty string (which disables the splash).

    Args:
    - terminal (`dict[str, Any]`): The ``terminal:`` config block.

    Returns:
    `str`: Absolute path to the ``.rgb565`` blob, or "" to skip the splash.

    """
    splash = terminal.get("splash", {}) or {}
    if not isinstance(splash, dict) or not splash.get("enabled", True):
        return ""
    rgb565 = splash.get("rgb565")
    if not rgb565:
        return ""
    root = Path(__file__).resolve().parent.parent.parent
    return str(root / str(rgb565))


def _resolve_users(terminal: dict[str, Any]) -> tuple[list[str], str]:
    r"""
    Resolve the selectable login users and the password mask from config.

    Args:
    - terminal (`dict[str, Any]`): The ``terminal:`` config block.

    Returns:
    `tuple[list[str], str]`: The user list (defaulting to ``["root"]``) and the
    password mask character.

    """
    login = terminal.get("login", {}) or {}
    login = login if isinstance(login, dict) else {}
    raw_users = login.get("users")
    users = (
        [str(u) for u in raw_users]
        if isinstance(raw_users, list) and raw_users
        else ["root"]
    )
    mask = str(login.get("password_mask", "*")) or "*"
    return users, mask


def load_bridge_config() -> BridgeConfig:
    r"""
    Resolve the terminal-bridge configuration from ``.whiskerframe.yaml``.

    Read the ``terminal:`` and ``cardkb:`` blocks and map them onto a
    `BridgeConfig`, using the live-verified hardware facts as fallbacks for any
    missing key so a fresh checkout still runs. The theme is loaded from the same
    config via ``load_theme``.

    Returns:
    `BridgeConfig`: The fully resolved bridge configuration.

    """
    config = _load_yaml_config()
    terminal: dict[str, Any] = config.get("terminal", {}) or {}
    cardkb: dict[str, Any] = config.get("cardkb", {}) or {}
    users, mask = _resolve_users(terminal)
    resolved = BridgeConfig(
        serial_port=str(terminal.get("serial_port", "/dev/ttyUSB0")),
        baud=_as_int(terminal.get("baud"), 115200),
        font_size=_as_int(terminal.get("font_size"), 2),
        keyframe_interval_s=_as_float(terminal.get("keyframe_interval_seconds"), 30.0),
        cardkb_bus=_as_int(cardkb.get("i2c_bus"), 0),
        cardkb_address=_as_int(cardkb.get("i2c_address"), 0x5F),
        cardkb_poll_s=_as_float(cardkb.get("poll_interval_seconds"), 0.05),
        users=users,
        password_mask=mask,
        splash_rgb565=_resolve_splash_path(terminal),
        theme=load_theme(config),
    )
    tracepoint(
        "terminal.config",
        serial_port=resolved.serial_port,
        font_size=resolved.font_size,
        users=len(resolved.users),
        splash=bool(resolved.splash_rgb565),
    )
    return resolved


def log(level: str, message: str) -> None:
    r"""
    Emit a single journald-friendly log line.

    Writes ``LEVEL: message`` to stdout (or stderr for ``ERROR``/``CRITICAL``) so
    systemd's journald captures it with sensible stream separation. No timestamp
    is added; journald timestamps each line.

    Args:
    - level (`str`): Severity label (e.g. ``INFO``, ``WARNING``, ``ERROR``).
    - message (`str`): The message body.

    Returns:
    `None`: The line is written to the appropriate stream.

    """
    stream = sys.stderr if level in {"ERROR", "CRITICAL"} else sys.stdout
    print(f"{level}: {message}", file=stream, flush=True)


def run(config: BridgeConfig) -> int:
    r"""
    Open the CardKB and run the terminal bridge loop.

    Construct the `TerminalBridge`, open the CardKB on the configured bus, and run
    the splash/login/shell loop over the keypad's ``robust_keys`` stream (which
    self-recovers from I2C glitches). The CardKB is closed on exit.

    Args:
    - config (`BridgeConfig`): The resolved bridge configuration.

    Returns:
    `int`: Process exit code (``0`` on a clean return).

    """
    bridge = TerminalBridge(config)
    keypad = CardKB(bus=config.cardkb_bus, address=config.cardkb_address)
    log(
        "INFO",
        f"terminal bridge started (serial {config.serial_port}, "
        f"cardkb bus {config.cardkb_bus} @ {config.cardkb_address:#04x})",
    )
    try:
        bridge.run(keypad.robust_keys(config.cardkb_poll_s))
    finally:
        keypad.close()
    return 0


def main() -> int:
    r"""
    Entry point: load configuration and run the terminal bridge.

    Returns:
    `int`: Process exit code.

    """
    return run(load_bridge_config())


if __name__ == "__main__":
    raise SystemExit(main())
