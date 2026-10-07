#!/usr/bin/env python3
"""
Komodo Core liveness probe (TSK-04), run on the Pi via ``uv run``.

Keep the uv-in-venv invariant: the ``komodo`` Ansible role verifies the stack by
invoking ``{{ venv_path }}/bin/uv run python -m komodo.healthcheck`` rather than a
raw curl, so the check runs inside the deterministic Pi venv like every other
Pi-side Python entry point.

Stdlib only (no Pillow, no third-party deps): a GET against Komodo Core's HTTP
port. Exit ``0`` when the server answers (any HTTP status proves the process is
up and listening), ``1`` otherwise. The host/port are overridable by env so the
same probe works if the port mapping changes.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:9120/"
TIMEOUT_S = 5.0


def check(url: str = DEFAULT_URL, timeout: float = TIMEOUT_S) -> bool:
    """
    Return ``True`` if Komodo Core answers an HTTP request at ``url``.

    Any HTTP response (including 4xx/redirects) proves the server is listening,
    so an :class:`urllib.error.HTTPError` still counts as healthy. Only a
    connection-level failure (refused, DNS, timeout) counts as unhealthy.

    Args:
    - url (`str`): The Core base URL to probe.
    - timeout (`float`): Per-request timeout in seconds.

    Returns:
    `bool`: ``True`` when the server responded, ``False`` on a connection failure.

    """
    try:
        with urllib.request.urlopen(url, timeout=timeout):  # noqa: S310 (fixed localhost URL)
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    """
    Entry point: probe Komodo Core and return a process exit code.

    Returns:
    `int`: ``0`` when Core answered, ``1`` otherwise.

    """
    url = os.environ.get("KOMODO_HEALTH_URL", DEFAULT_URL)
    ok = check(url)
    print(f"komodo health: {'OK' if ok else 'DOWN'} ({url})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
