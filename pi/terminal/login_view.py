r"""
Pure rendering of the login state machine onto a terminal :class:`.grid.Grid`.

Paint a :class:`.login.LoginState` onto a blank grid so the bridge can diff it
and emit the usual ``DRAW_CELLS`` runs: a title line, the selectable user list
(the highlighted/selected user drawn in the theme accent, the rest in the default
foreground), and -- on the password screen -- a prompt plus the masked password
line. An optional transient error message (e.g. "login failed") can be shown
below the prompt.

The password is **never** rendered in plaintext: this module only ever draws
:meth:`.login.LoginState.masked`, which is a string of mask characters, so a
password cannot leak onto the screen. The module is pure (no I/O, no hardware)
and total: all text is clipped to the grid width and rows outside the grid are
skipped, so a tiny grid or a long user list can never raise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .grid import Grid

if TYPE_CHECKING:
    from .login import LoginState
    from .theme import Theme

__all__ = [
    "LOGIN_TITLE",
    "render_login",
]

LOGIN_TITLE: str = "cyberdeck login"
"""Title drawn on the first row of the login screen."""

_PASSWORD_PROMPT: str = "password:"  # noqa: S105 - a UI label, not a secret
"""Prompt label drawn above the masked password line on the password screen."""

_TITLE_ROW: int = 0
_FIRST_USER_ROW: int = 2
_SELECTED_PREFIX: str = "> "
_UNSELECTED_PREFIX: str = "  "


def _put_text(
    grid: Grid,
    row: int,
    col: int,
    text: str,
    fg: int,
    bg: int,
) -> None:
    """
    Write a clipped run of text onto the grid at ``(row, col)``.

    Draw ``text`` one character per cell starting at ``(row, col)``, stopping at
    the grid's right edge. Rows outside the grid are ignored, so the call is
    always safe regardless of grid size.

    Args:
    - grid (`Grid`): The target grid.
    - row (`int`): Target row (ignored if out of range).
    - col (`int`): Starting column.
    - text (`str`): The text to draw.
    - fg (`int`): RGB565 foreground colour.
    - bg (`int`): RGB565 background colour.

    Returns:
    `None`: The grid is mutated in place.

    """
    if not 0 <= row < grid.rows:
        return
    grid.set_cursor(row, max(0, col))
    for char in text:
        if grid.cursor_col >= grid.cols - 1 and grid.cursor_row != row:
            break
        if grid.cursor_row != row:
            break
        grid.put_char(char, fg, bg)


def _render_users(grid: Grid, state: LoginState, theme: Theme) -> int:
    """
    Draw the selectable user list and return the next free row.

    Draw each configured user on its own row starting at :data:`_FIRST_USER_ROW`,
    prefixing the selected user with ``> `` and painting it in the accent colour
    while the others use the default foreground. Users beyond the grid height are
    skipped.

    Args:
    - grid (`Grid`): The target grid.
    - state (`LoginState`): The login state holding the users and selection.
    - theme (`Theme`): The palette (accent for the selected user).

    Returns:
    `int`: The first row below the user list (for the password area).

    """
    accent = theme.accents.get("pink", theme.fg)
    row = _FIRST_USER_ROW
    for index, user in enumerate(state.users):
        if row >= grid.rows:
            break
        selected = index == state.selected
        prefix = _SELECTED_PREFIX if selected else _UNSELECTED_PREFIX
        colour = accent if selected else theme.fg
        _put_text(grid, row, 0, f"{prefix}{user}", colour, theme.bg)
        row += 1
    return row + 1


def render_login(
    state: LoginState,
    theme: Theme,
    cols: int,
    rows: int,
    error: str = "",
) -> Grid:
    """
    Render a login state onto a fresh grid ready for diffing.

    Build a blank :class:`.grid.Grid` of ``cols`` x ``rows`` in the theme's
    default colours and paint the title, the user list (selected user in the
    accent colour), and -- when the password screen is active -- the password
    prompt and the masked password line. An optional ``error`` string is drawn
    below the prompt in the theme's red ANSI colour.

    The password is only ever drawn via :meth:`.login.LoginState.masked`
    (mask characters), so plaintext can never reach the grid.

    Args:
    - state (`LoginState`): The login UI state to render.
    - theme (`Theme`): The palette and accents to colour the screen.
    - cols (`int`): Grid columns (from the active geometry).
    - rows (`int`): Grid rows (from the active geometry).
    - error (`str`, optional): Transient error message to show. Defaults to "".

    Returns:
    `Grid`: A freshly painted grid for the current login screen.

    """
    from .login import LoginScreen

    grid = Grid(cols, rows, theme.fg, theme.bg)
    _put_text(
        grid,
        _TITLE_ROW,
        0,
        LOGIN_TITLE,
        theme.accents.get("purple", theme.fg),
        theme.bg,
    )
    next_row = _render_users(grid, state, theme)
    if state.screen is LoginScreen.PASSWORD:
        _put_text(grid, next_row, 0, _PASSWORD_PROMPT, theme.fg, theme.bg)
        _put_text(
            grid,
            next_row,
            len(_PASSWORD_PROMPT) + 1,
            state.masked(),
            theme.fg,
            theme.bg,
        )
        if error:
            red = theme.ansi[1] if len(theme.ansi) > 1 else theme.fg
            _put_text(grid, next_row + 1, 0, error, red, theme.bg)
    return grid
