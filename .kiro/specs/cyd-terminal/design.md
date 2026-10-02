# CYD Terminal — Design

A real terminal on the CYD screen, connected to the Raspberry Pi, typed on the
M5Stack CardKB, styled in the piiiiink palette (blurple background, pink text,
blue/purple accents). Builds on the existing `whiskerframe` command path, the
CYD firmware, the UPS/CardKB I2C work, and the field-robustness rule (the deck
runs unattended; nothing may crash or wedge it).

## Overview

```text
 CardKB (I2C-0 0x5F) ──keys──▶ ┐
                               │  terminal_bridge (Pi daemon)
 bash login shell ◀──PTY──────▶┤   - owns a PTY running `bash -l`
   (stdout/stderr) ──bytes────▶│   - VT100-subset emulator -> cell grid
                               │   - diffs grid, emits cell/row/scroll draws
                               └──framed serial──▶ CYD firmware ──▶ ILI9341
```

Three parts:

1. **Pi `terminal_bridge` daemon** (`pi/terminal/`): spawns a PTY running a real
   `bash -l` login shell, feeds CardKB keypresses to the PTY, parses shell output
   through a VT100-subset emulator into a character grid, diffs the grid, and
   sends incremental draw commands to the CYD over serial. Full root console.
2. **New firmware draw ops** (`firmware/cyd_display_link/`): a compact
   `DRAW_CELLS` (run of characters at a row/col in fg/bg) and `SCROLL` (shift the
   text region up N rows) so a keystroke never triggers a full-screen redraw at
   115200 baud.
3. **`whiskerframe` terminal support**: a `TerminalGrid` model + builders for the
   new ops, a piiiiink `Theme`, and a resizable grid geometry.

## Serial bandwidth (why incremental)

115200 baud ≈ 11.5 KB/s. A full 320×240 redraw is ~150 KB — seconds per frame,
unusable. So the emulator keeps the previous grid and only emits the cells that
changed, plus a dedicated `SCROLL` op (shifting rows on-device costs one small
command instead of redrawing every line). Typical keystroke => a handful of
`DRAW_CELLS` bytes.

## New wire ops (extend the existing protocol)

Current opcodes: `DRAW_TEXT 0x01`, `DRAW_RECT 0x02`, `CLEAR 0x10`, `FLUSH 0x1F`.
Add:

- `DRAW_CELLS 0x03` — a run of fixed-cell glyphs on one text row:

  ```text
  col      : uint16   starting column (cell units)
  row      : uint16   starting row (cell units)
  fg       : uint16   RGB565 foreground
  bg       : uint16   RGB565 background
  font_size: uint8    cell font size (grid geometry)
  len      : uint16   number of characters
  chars    : bytes    `len` bytes, one per cell (CP437/ASCII)
  ```

  Firmware draws each glyph at `(col*cw, row*ch)` using the fixed-cell metrics,
  painting the cell background first (so overwrites are clean).

- `SCROLL 0x04` — shift the text region up (or down) by whole rows:

  ```text
  rows     : int8     signed row count (+up, -down)
  fill     : uint16   RGB565 color for the vacated rows
  top      : uint16   first row of the scroll region (cell units)
  bottom   : uint16   last row of the scroll region (cell units)
  ```

  Firmware uses a fast rect copy (TFT_eSPI `readRect`/`pushRect` or a row-band
  blit) and fills the newly exposed rows with `fill`.

Both are additive; `frame.h` already discards unknown opcodes, so older firmware
degrades safely. The host only sends new ops after confirming firmware support
(a `HELLO`/version handshake is a stretch goal; v1 assumes the flashed firmware
is current).

## VT100 subset

Enough for a login shell, `ls`, `vim`-lite, `htop`-lite; not full ncurses:

- Printable chars advance the cursor; wrap at the right edge.
- `\n` line feed, `\r` carriage return, `\b` backspace, `\t` tab (8-col).
- `ESC[` CSI: cursor up/down/left/right (`A/B/C/D`), absolute position
  (`H`/`f`), erase in line (`K`), erase in display (`J`), SGR colors (`m`:
  reset, 30-37/40-47, 90-97/100-107, bold).
- Line scroll when the cursor advances past the last row -> emit `SCROLL` +
  redraw the new bottom row.
- Unknown escape sequences are consumed and ignored (never corrupt the grid).

The emulator is a pure state machine over bytes -> grid mutations, so it is unit-
testable on the host without hardware (property tests mirror the decoder tests).

## piiiiink theme (a11y-corrected, RGB565)

The palette is derived from the user's piiiiink VS Code theme and **corrected for
WCAG AA contrast** against the blurple terminal background `#191a28`. Every colour
below is >= 4.5:1 on that background (verified). Hues stay in the piiiiink family
(pink text, blurple bg, purple/blue/cyan accents). All values live in
`.whiskerframe.yaml` `terminal.theme` (RGB565), not hard-coded.

| Role | Hex | Contrast | RGB565 |
| --- | --- | --- | --- |
| background (blurple) | `#191a28` | - | `0x18C5` |
| foreground (pink) | `#ffb3e6` | 10.5 | `0xFD9C` |
| cursor (cyan) | `#2dd8ff` | 10.2 | `0x2EDF` |
| accent pink | `#ff6fd0` | 6.9 | `0xFB7A` |
| accent purple | `#b9a9ff` | 8.4 | `0xBD5F` |
| accent blue | `#8f98ff` | 6.6 | `0x8CDF` |

ANSI 0-15 are remapped into the same family and each brightened to pass AA (the
original theme's `ansiBlack #666666`, `ansiBlue #2472c8`, `ansiRed #cd3131` failed
AA on this bg; they are corrected). The full 16-colour RGB565 ANSI table is in
`terminal.theme.ansi`. VT100 `SGR` codes map onto this table; default fg = pink,
default bg = blurple.

The corrected theme is also saved back as a VS Code theme at
`assets/themes/piiiiink-a11y.json` so the desktop editor and the deck share one
coherent, accessible palette.

## Resizable terminal

Grid geometry derives from font size and the 320×240 panel:

- size 1 → cell 6×8 → 53×30 grid
- size 2 → cell 12×16 → 26×15 grid
- size 3 → cell 18×24 → 17×10 grid

The daemon exposes the current size in config (`terminal.font_size`) and accepts
a runtime resize (a control key chord on the CardKB, e.g. a Fn+/- or an escape
command), which: recomputes the grid, informs the PTY of the new size via
`TIOCSWINSZ` (so programs reflow), clears, and repaints. `whiskerframe` provides
`TerminalGeometry(font_size) -> (cols, rows, cell_w, cell_h)`.

## Login, logout, and splash

The deck does **not** boot straight into root. The flow is:

```text
power on ──▶ SPLASH image ──▶ LOGIN screen ──▶ shell (as chosen user) ──▶ `logout` ──▶ LOGIN screen
```

- **Splash:** while the Pi boots, the bridge (or an early boot unit) shows a splash
  image on the CYD. The image path is config (`terminal.splash.image`, default
  `assets/images/cess/Lyra and Dreanne Christmas Night Market.png`). It is
  **pre-converted to RGB565 once on the PC programmer** (a `just` recipe) into
  `terminal.splash.rgb565`, which is synced to the Pi; the Pi never runs Pillow or
  converts at boot — it only reads the ready `.rgb565` blob and sends it via
  `DRAW_IMAGE` (chunked raw rows). Shown until the login screen is ready.
- **Login screen:** lists the configured selectable users
  (`terminal.login.users`), lets the user pick one (CardKB arrow/enter), then
  prompts for the password. **Typed characters are echoed as `*`** (mask from
  `terminal.login.password_mask`), never plaintext. Authentication is **real
  system auth** (PAM via `pam`/`simplepam`, or a `su -c true <user>` check) — the
  bridge does not store or compare passwords itself. On success it starts the PTY
  shell as that user (`su - <user>` / set the PTY's uid), so the shell runs with
  that user's privileges, not unconditionally root.
- **Logout:** the `logout` shell builtin (or shell exit / EOF) ends the PTY
  session; the bridge detects EOF, clears the screen, and returns to the LOGIN
  screen (it does NOT auto-respawn a root shell). A fresh login is required.
- **Robustness:** the login screen itself is the safe idle state — if the shell
  dies for any reason, the deck falls back to login, never to an unauthenticated
  root prompt.

### Security

This replaces the earlier "boots to root" note: the CYD now gates on a real
system login (user selection + masked password + PAM/su auth). Physical access no
longer yields an unauthenticated root console. Password input is masked and never
logged or echoed in plaintext. Choosing the `root` user still grants root after a
correct root password — that is intended and gated by the password.

## Robustness (field rule)

- The daemon never crashes: PTY EOF (shell exit) -> respawn `bash -l`; serial
  write error -> reopen the port with bounded backoff; CardKB error -> use
  `robust_keys` (already self-recovering).
- systemd unit `Restart=always`, `RestartSec`.
- On start it clears the screen and repaints from a blank grid, so a mid-session
  CYD reset recovers on the next full repaint (periodic keyframe: every N
  seconds or on serial reopen, send a full grid repaint).
- No interactive prompts in the daemon path.

## Modules

```text
pi/terminal/
  __init__.py
  vt.py          # VT100-subset emulator: bytes -> Grid mutations (pure)
  grid.py        # Grid + Cell model, diff -> list of change runs (pure)
  theme.py       # piiiiink palette, SGR -> RGB565 mapping (pure)
  login.py       # login screen: user select + masked password + PAM/su auth (pure UI + auth call)
  splash.py      # boot splash image -> RGB565 blit
  bridge.py      # PTY <-> CardKB <-> serial glue daemon (I/O, robustness)
  daemon.py      # entry point: load config, run bridge, systemd target
  terminal.service
  install.sh
whiskerframe/
  terminal.py    # TerminalGeometry, DrawCells/Scroll models + serialize
firmware/cyd_display_link/
  render.h       # + render_cells(), render_scroll()
  protocol/frame # DRAW_CELLS 0x03, SCROLL 0x04 handling in dispatch
```

## Testing (host, no hardware)

- `vt.py`: property/unit tests — printables fill cells; CR/LF/BS/TAB; CSI cursor
  moves; SGR colour; scroll on overflow; unknown escapes ignored (grid intact).
- `grid.py`: diff emits exactly the changed runs; full repaint on request.
- `theme.py`: SGR code -> RGB565 mapping is total and stable.
- `whiskerframe/terminal.py`: DrawCells/Scroll serialize/decode round-trip; geometry
  math for each font size.
- Firmware render_cells/render_scroll: reviewed by inspection + a host model for
  the cell/scroll math (compiled on-device during flash).

## Decisions / rationale

- **Incremental cell/scroll ops over full redraw** — mandated by 115200
  bandwidth; keeps latency per keystroke tiny.
- **Real `bash -l`** — full console as requested; the daemon is a transport, not
  a restricted shell.
- **VT100 subset, unknown-escape-safe** — covers real shell use without the cost
  and risk of full emulation; never corrupts the grid.
- **Config-driven theme + size** — reproducible-build rule; palette/geometry/login/
  splash in `.whiskerframe.yaml`, not hard-coded. The live `.whiskerframe.yaml` is
  per-user and gitignored; `.whiskerframe.example.yaml` is the committed template
  (loader falls back to the example on a fresh clone).
- **Respawn/reopen everywhere** — field-robustness rule; the deck can't be
  serviced on the go.

## Security note

This renders a root `bash` login shell on an external display with CardKB input.
Anyone with physical access to the deck has a root console. That is the intended
design (it is the user's personal cyberdeck), but it is recorded here as a
deliberate decision: no auth gate sits between the CardKB and root.
