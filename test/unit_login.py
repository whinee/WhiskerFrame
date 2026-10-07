"""
Unit test for the login UI state machine and guarded auth adapter.

**Validates: Requirements (cyd-terminal design: login gate)**

Assert the pure :class:`terminal.login.LoginState` behavior:

- user-select navigation (up/down wraps; enter advances to the password screen);
- password masking -- the display is only mask characters while the hidden buffer
  holds the real characters;
- backspace deletes the last character;
- enter on the password screen emits a `SubmitEvent` with the chosen user and the
  real password;
- :func:`terminal.login.authenticate` raises a clear error when ``simplepam`` is
  not installed (the guard), without the state machine needing it.

The script is pure (no hardware, no Pillow, no simplepam). It adds ``pi/`` to
``sys.path``, runs as ``uv run python test/unit_login.py``, prints ``PASS`` on
success, and exits non-zero on the first failure.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pi"))

from terminal.login import (
    LoginScreen,
    LoginState,
    SubmitEvent,
    authenticate,
)

_UP: int = 0xB5
_DOWN: int = 0xB6
_LEFT: int = 0xB4
_ESC: int = 0x1B
_ENTER: int = 0x0D
_BACKSPACE: int = 0x08


def check_user_navigation() -> None:
    """
    Assert up/down navigation wraps and enter advances to the password screen.

    Raises:
    - `AssertionError`: If navigation or screen transition is wrong.

    Returns:
    `None`: Returns nothing on success.

    """
    state = LoginState(users=["root", "lyra", "guest"])
    assert state.selected_user == "root"
    state.feed_key(_DOWN)
    assert state.selected_user == "lyra"
    state.feed_key(_UP)
    state.feed_key(_UP)  # wrap past 0 -> last
    assert state.selected_user == "guest"
    state.feed_key(_ENTER)
    assert state.screen is LoginScreen.PASSWORD


def check_password_masking() -> None:
    """
    Assert the display is all mask chars while the buffer holds real chars.

    Raises:
    - `AssertionError`: If the mask or submitted password is wrong.

    Returns:
    `None`: Returns nothing on success.

    """
    state = LoginState(users=["lyra"], mask="*")
    state.feed_key(_ENTER)  # to password screen
    for ch in b"s3cr3t":
        assert state.feed_key(ch) is None
    assert state.masked() == "******", "display must be all mask characters"
    assert "s3cr3t" not in state.masked(), "plaintext must never appear in display"

    event = state.feed_key(_ENTER)
    assert isinstance(event, SubmitEvent)
    assert event.user == "lyra"
    expected_password = "s3cr3t"  # noqa: S105
    assert event.password == expected_password, "submit must carry the real password"


def check_backspace() -> None:
    """
    Assert backspace removes the last entered character.

    Raises:
    - `AssertionError`: If backspace does not shrink the buffer.

    Returns:
    `None`: Returns nothing on success.

    """
    state = LoginState(users=["lyra"])
    state.feed_key(_ENTER)
    for ch in b"abc":
        state.feed_key(ch)
    state.feed_key(_BACKSPACE)
    assert state.masked() == "**"
    event = state.feed_key(_ENTER)
    assert isinstance(event, SubmitEvent)
    assert event.password == "ab"  # noqa: S105


def check_left_arrow_navigation() -> None:
    """
    Assert pressing Left arrow or Esc from password screen resets to user select.

    Raises:
    - `AssertionError`: If pressing Left or Esc fails to return to user select.

    Returns:
    `None`: Returns nothing on success.

    """
    state = LoginState(users=["root", "neko"])
    state.feed_key(_ENTER)
    assert state.screen is LoginScreen.PASSWORD
    for ch in b"secret":
        state.feed_key(ch)
    assert state.masked() == "******"

    # Pressing Left arrow resets to USER_SELECT and clears password
    assert state.feed_key(_LEFT) is None
    assert state.screen is LoginScreen.USER_SELECT
    assert state.masked() == ""

    # Re-enter password screen and test Esc key
    state.feed_key(_ENTER)
    assert state.screen is LoginScreen.PASSWORD
    for ch in b"xyz":
        state.feed_key(ch)
    assert state.feed_key(_ESC) is None
    assert state.screen is LoginScreen.USER_SELECT
    assert state.masked() == ""


def check_clear_password() -> None:
    """
    Assert clear_password empties the buffer while staying on the current screen.

    Raises:
    - `AssertionError`: If password is not cleared or screen changes.

    Returns:
    `None`: Returns nothing on success.

    """
    state = LoginState(users=["neko"])
    state.feed_key(_ENTER)
    for ch in b"secret":
        state.feed_key(ch)
    assert state.masked() == "******"
    state.clear_password()
    assert state.masked() == ""
    assert state.screen is LoginScreen.PASSWORD


def check_empty_users_rejected() -> None:
    """
    Assert constructing with an empty user list raises.

    Raises:
    - `AssertionError`: If no `ValueError` is raised.

    Returns:
    `None`: Returns nothing on success.

    """
    try:
        LoginState(users=[])
    except ValueError:
        return
    msg = "empty user list must raise ValueError"
    raise AssertionError(msg)


def check_authenticate_guard() -> None:
    """
    Assert authenticate() raises clearly when simplepam is absent.

    Only runs the guard assertion when ``simplepam`` is genuinely not installed;
    if it is present, the guard cannot fire and the check is skipped.

    Raises:
    - `AssertionError`: If authenticate does not raise `RuntimeError` when the
      dependency is missing.

    Returns:
    `None`: Returns nothing on success (or when skipped).

    """
    if importlib.util.find_spec("simplepam") is not None:
        return  # dependency present; the guard path is unreachable here
    try:
        authenticate("nobody", "x")
    except RuntimeError:
        return
    msg = "authenticate must raise RuntimeError without simplepam"
    raise AssertionError(msg)


def main() -> None:
    """
    Run the login checks and report the outcome.

    Returns:
    `None`: Exits ``1`` on failure; prints ``PASS`` otherwise.

    """
    try:
        check_user_navigation()
        check_password_masking()
        check_backspace()
        check_left_arrow_navigation()
        check_clear_password()
        check_empty_users_rejected()
        check_authenticate_guard()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
