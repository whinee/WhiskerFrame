"""
Load reproducible cyberdeck configuration from ``.env`` and ``.whiskerframe.yaml``.

Centralize the project's non-code configuration so scripts stay reproducible and
free of hard-coded hosts, keys, and hardware facts (see the reproducible-build
rule). Environment/secret-ish values (Pi host, user, key path, venv path) come
from ``.env`` (gitignored; ``.env.example`` is the committed template). Project
and hardware facts (verified components, UPS/INA219 parameters, CYD serial port)
come from the committed ``.whiskerframe.yaml``.

Both files are optional at import time: missing keys fall back to documented
defaults so a fresh checkout still runs, while a populated ``.env`` /
``.whiskerframe.yaml`` overrides them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from debug import tracepoint
from dotenv import load_dotenv

__all__ = [
    "PROJECT_ROOT",
    "env",
    "load_yaml_config",
]

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
"""Absolute path to the repository root (the parent of ``scripts/``)."""

# Load .env from the project root once at import; real environment variables win.
load_dotenv(PROJECT_ROOT / ".env")


def env(name: str, default: str) -> str:
    """
    Return an environment variable, falling back to a documented default.

    Read ``name`` from the process environment (populated from ``.env`` by
    :func:`dotenv.load_dotenv` at import), returning ``default`` when it is unset
    so a fresh checkout without a ``.env`` still runs.

    Args:
    - name (`str`): Environment variable name to read.
    - default (`str`): Value to use when the variable is unset.

    Returns:
    `str`: The configured value or the default.

    """
    value = os.environ.get(name)
    tracepoint("config.env", name=name, using_default=value is None)
    return value if value is not None else default


def load_yaml_config(path: Path | None = None) -> dict[str, Any]:
    """
    Load the ``.whiskerframe.yaml`` project configuration.

    Parse the committed project/hardware configuration into a dictionary. A
    missing file yields an empty dict so callers can apply their own defaults,
    keeping the config optional for a minimal checkout.

    Args:
    - path (`Path | None`, optional): Explicit config path. Defaults to ``.whiskerframe.yaml`` (falling back to ``.whiskerframe.example.yaml``) at the project root.

    Returns:
    `dict[str, Any]`: The parsed configuration mapping (empty when absent).

    """
    if path is not None:
        config_path = path
    else:
        # Prefer the user's live, gitignored config; fall back to the committed
        # example so a fresh clone (before the user copies it) still works.
        live = PROJECT_ROOT / ".whiskerframe.yaml"
        example = PROJECT_ROOT / ".whiskerframe.example.yaml"
        config_path = live if live.is_file() else example
    if not config_path.is_file():
        tracepoint("config.yaml", path=config_path, keys=0)
        return {}
    loaded = yaml.safe_load(config_path.read_text())
    result = loaded if isinstance(loaded, dict) else {}
    tracepoint("config.yaml", path=config_path, keys=len(result))
    return result
