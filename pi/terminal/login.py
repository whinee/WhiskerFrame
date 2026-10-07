"""
Pure login UI state machine plus a guarded PAM authentication adapter.

Drive the CYD login gate without any I/O: :class:`LoginState` is a pure state
machine fed CardKB keypress bytes that walks user selection (up/down/enter) then
masked password entry (printable keys append to a hidden buffer and emit a mask
character for display; backspace deletes; enter submits), surfacing the current
screen, the selected user, the masked display string, and -- on enter -- a
:class:`SubmitEvent` carrying the chosen user and the real password.

Authentication is kept separate from the UI so the state machine and its tests
run with no ``simplepam`` installed: :func:`authenticate` imports ``simplepam``
lazily and raises a clear error only when actually called without it. The
password is never logged, never echoed in plaintext, and is not retained beyond
the auth call (the caller clears the buffer).

This module is pure apart from the guarded ``simplepam`` call in
:func:`authenticate`; it imports no hardware driver and no Pillow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

__all__ = [
    "DEFAULT_MASK",
    "LoginScreen",
    "LoginState",
    "SubmitEvent",
    "authenticate",
]

DEFAULT_MASK: str = "*"
"""Default character echoed for each password keystroke."""

_KEY_ENTER: frozenset[int] = frozenset({0x0D, 0x0A})
_KEY_BACKSPACE: frozenset[int] = frozenset({0x08, 0x7F})
_KEY_UP: int = 0xB5  # M5Stack CardKB up arrow
_KEY_DOWN: int = 0xB6  # M5Stack CardKB down arrow
_KEY_LEFT: int = 0xB4  # M5Stack CardKB left arrow
_KEY_ESC: int = 0x1B  # Escape key
_PRINTABLE_MIN: int = 0x20
_PRINTABLE_MAX: int = 0x7E


class LoginScreen(Enum):
    """
    Which screen the login flow is currently showing.

    Attributes:
    - USER_SELECT: Choosing a user from the configured list.
    - PASSWORD: Entering the masked password for the selected user.

    """

    USER_SELECT = auto()
    PASSWORD = auto()


@dataclass(frozen=True)
class SubmitEvent:
    """
    A completed login submission carrying the chosen user and password.

    Emitted once when the password entry is confirmed with enter. The password
    is the plaintext the caller passes straight to :func:`authenticate`; callers
    MUST NOT log or persist it.

    Attributes:
    - user (`str`): The selected username.
    - password (`str`): The entered plaintext password.

    """

    user: str
    password: str


@dataclass
class LoginState:
    """
    A pure login UI state machine over CardKB keypress bytes.

    Track the current screen, the selected user index, and a hidden password
    buffer. Keys are fed one at a time via :meth:`feed_key`, which returns a
    :class:`SubmitEvent` exactly when a password is confirmed. The display never
    exposes the password: :meth:`masked` returns only mask characters.

    Attributes:
    - users (`list[str]`): The selectable usernames (non-empty).
    - mask (`str`): The character echoed per password keystroke.
    - screen (`LoginScreen`): The current screen.
    - selected (`int`): Index into ``users`` of the highlighted/selected user.

    """

    users: list[str]
    mask: str = DEFAULT_MASK
    screen: LoginScreen = LoginScreen.USER_SELECT
    selected: int = 0
    _password: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """
        Validate the user list and normalize the mask.

        Raises:
        - `ValueError`: If ``users`` is empty.

        Returns:
        `None`: The instance is left ready to accept keys.

        """
        if not self.users:
            msg = "LoginState requires at least one user."
            raise ValueError(msg)
        if not self.mask:
            self.mask = DEFAULT_MASK
        self.selected = max(0, min(self.selected, len(self.users) - 1))

    @property
    def selected_user(self) -> str:
        """
        Return the currently selected username.

        Returns:
        `str`: The user at the current selection index.

        """
        return self.users[self.selected]

    def masked(self) -> str:
        """
        Return the masked password display string.

        The returned string is the mask character repeated once per entered
        character; it never contains any real password character.

        Returns:
        `str`: The display string of mask characters.

        """
        return self.mask * len(self._password)

    def feed_key(self, key: int) -> SubmitEvent | None:
        """
        Advance the login flow by one CardKB key byte.

        On the user-select screen, up/down change the selection and enter moves
        to the password screen. On the password screen, printable keys append to
        the hidden buffer, backspace deletes the last character, and enter emits
        a :class:`SubmitEvent` with the chosen user and plaintext password.

        Args:
        - key (`int`): The CardKB key byte in ``[0, 255]``.

        Returns:
        `SubmitEvent | None`: The submission on password confirm, else ``None``.

        """
        if self.screen is LoginScreen.USER_SELECT:
            self._feed_user_select(key)
            return None
        return self._feed_password(key)

    def _feed_user_select(self, key: int) -> None:
        """
        Handle a key on the user-selection screen.

        Args:
        - key (`int`): The CardKB key byte.

        Returns:
        `None`: Selection/screen state is updated in place.

        """
        if key == _KEY_UP:
            self.selected = (self.selected - 1) % len(self.users)
        elif key == _KEY_DOWN:
            self.selected = (self.selected + 1) % len(self.users)
        elif key in _KEY_ENTER:
            self.screen = LoginScreen.PASSWORD
            self._password = []

    def _feed_password(self, key: int) -> SubmitEvent | None:
        """
        Handle a key on the masked password-entry screen.

        Args:
        - key (`int`): The CardKB key byte.

        Returns:
        `SubmitEvent | None`: The submission when enter is pressed, else ``None``.

        """
        if key in (_KEY_LEFT, _KEY_ESC):
            self.reset_to_user_select()
            return None
        if key in _KEY_ENTER:
            if not self._password:
                return None
            return SubmitEvent(
                user=self.selected_user,
                password="".join(self._password),
            )
        self._update_password_buffer(key)
        return None

    def _update_password_buffer(self, key: int) -> None:
        """
        Modify the password buffer for backspace or printable keystrokes.

        Args:
        - key (`int`): The CardKB key byte.

        Returns:
        `None`: The hidden buffer is updated in place.

        """
        if key in _KEY_BACKSPACE and self._password:
            self._password.pop()
        elif _PRINTABLE_MIN <= key <= _PRINTABLE_MAX:
            self._password.append(chr(key))

    def clear_password(self) -> None:
        """
        Clear the hidden password buffer without changing the screen.

        Returns:
        `None`: Hidden buffer is cleared in place.

        """
        self._password = []

    def reset_to_user_select(self) -> None:
        """
        Return to the user-selection screen and clear the password buffer.

        Used after a submission (success or failure) so no password lingers.

        Returns:
        `None`: Screen state is reset and the hidden buffer is cleared in place.

        """
        self.screen = LoginScreen.USER_SELECT
        self._password = []


def authenticate(user: str, password: str) -> bool:
    """
    Authenticate a user against the system via PAM (``simplepam``).

    Import ``simplepam`` lazily so the pure state machine and its tests run
    without the dependency installed. The password is passed straight through to
    PAM and never logged or stored by this adapter.

    Args:
    - user (`str`): The username to authenticate.
    - password (`str`): The plaintext password to verify.

    Raises:
    - `RuntimeError`: If ``simplepam`` is not installed.

    Returns:
    `bool`: ``True`` if PAM accepts the credentials, else ``False``.

    """
    try:
        import simplepam  # type: ignore[import-untyped]
    except ImportError as exc:
        msg = (
            "simplepam is required for login authentication; install the Pi "
            "runtime dependency (simplepam>=0.1.5)."
        )
        raise RuntimeError(msg) from exc
    return bool(simplepam.authenticate(user, password))
