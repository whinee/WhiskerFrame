"""
Reliability test suite integration for host-side test runners.

Exposes test cases from `scripts/reliability/` to standard discovery runners
(`pytest test/` and `python3 -m unittest discover test`).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.reliability.test_ctrl_latch_edge_cases import (  # noqa: E402
    TestCtrlLatchEdgeCases,
    TestCtrlLatchProperties,
)
from scripts.reliability.test_login_logout_loop import (  # noqa: E402
    TestLoginLogoutLoop,
)
from scripts.reliability.test_serial_resilience import (  # noqa: E402
    TestSerialResilience,
)
from scripts.reliability.test_terminal_pty_soak import (  # noqa: E402
    TestTerminalPtySoak,
)

__all__ = [
    "TestCtrlLatchEdgeCases",
    "TestCtrlLatchProperties",
    "TestLoginLogoutLoop",
    "TestSerialResilience",
    "TestTerminalPtySoak",
]
