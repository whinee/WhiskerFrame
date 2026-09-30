"""
Property test for Pi_Host environment-check reporting (Req 6.3).

**Property 10: Environment check reports exactly the missing components**

**Validates: Requirements 6.3**

For any combination of presence flags over ``{python3, pip, pyserial}``, the
pure reporting layer reports exactly the components that are absent:
`missing_components` returns precisely the absent component names in `COMPONENTS`
order, and `format_report` sets ``all_present`` true iff nothing is missing.

The script is pure (no SSH, no network): it drives `missing_components` and
`format_report` with hypothesis-generated presence flags, runs as
``uv run python test/prop_env_check_reporting.py``, prints ``PASS`` on success,
and exits non-zero on the first falsifying example.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pi_env_check import (
    COMPONENTS,
    ComponentPresence,
    format_report,
    missing_components,
)


@settings(max_examples=300)
@given(python3=st.booleans(), pip=st.booleans(), pyserial=st.booleans())
def check_reports_exactly_missing(
    python3: bool,
    pip: bool,
    pyserial: bool,
) -> None:
    """
    Assert the report names exactly the absent components (Property 10).

    Args:
    - python3 (`bool`): Whether ``python3`` is present.
    - pip (`bool`): Whether ``pip`` is present.
    - pyserial (`bool`): Whether ``pyserial`` is present.

    Raises:
    - `AssertionError`: If the missing list is not the absent components in
      `COMPONENTS` order, or ``all_present`` disagrees with the missing list.

    Returns:
    `None`: This check returns nothing when reporting is correct.

    """
    presence = ComponentPresence(python3=python3, pip=pip, pyserial=pyserial)
    flags = {"python3": python3, "pip": pip, "pyserial": pyserial}
    expected = tuple(name for name in COMPONENTS if not flags[name])

    assert missing_components(presence) == expected

    report = format_report(presence)
    assert report.missing == expected
    assert report.all_present == (len(expected) == 0)


def main() -> None:
    """
    Run the Property 10 check and report success.

    Raises:
    - `AssertionError`: If hypothesis finds a falsifying example.

    Returns:
    `None`: This entry point returns nothing.

    """
    check_reports_exactly_missing()
    print("PASS")


if __name__ == "__main__":
    main()
