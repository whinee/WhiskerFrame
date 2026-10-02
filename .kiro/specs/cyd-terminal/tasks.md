# CYD Terminal — Tasks

Incremental build. Each wave ends at a point you can approve before the next.
Pure/host-testable work first; firmware and the live daemon last. Honors
field-robustness (self-recover), reproducible-build (config-driven), lint-and-fix
(ruff/black/mypy), api-docs, changelog.

Legend: `[ ]` todo · `*` optional test task · `[MANUAL]` needs hardware.

## Wave A — host-side pure core (no hardware)

- [ ] A1. `whiskerframe/terminal.py`: `TerminalGeometry(font_size) -> cols/rows/cell_w/cell_h`
      for sizes 1-3; `DrawCells` + `Scroll` pydantic models matching the wire layout.
    - [ ]* A1t. round-trip + geometry property tests.
- [ ] A2. Extend `whiskerframe/protocol.py`: opcodes `DRAW_CELLS 0x03`, `SCROLL 0x04`,
      and `DRAW_IMAGE 0x05` (chunked RGB565 rows for the splash); serialize/decode
      for each (CRC/framing unchanged).
    - [ ]* A2t. round-trip property tests for the two new ops.
- [ ] A3. `pi/terminal/grid.py`: `Cell`, `Grid` (cols×rows), cursor, `diff(prev)`
      -> change runs, `full_repaint()`; pure.
    - [ ]* A3t. diff emits exactly changed runs; full repaint covers all cells.
- [ ] A4. `pi/terminal/theme.py`: load the a11y piiiiink palette from
      `.whiskerframe.yaml` `terminal.theme` + `sgr_to_rgb565` total map (16-colour ANSI).
    - [ ]* A4t. SGR map totality test.
- [ ] A5. `pi/terminal/vt.py`: VT100-subset emulator (printable, CR/LF/BS/TAB,
      CSI cursor/erase, SGR, scroll-on-overflow, unknown-escape-safe) -> Grid mutations; pure.
    - [ ]* A5t. emulator property/unit tests (the big one).
- [ ] A6. CHECKPOINT: `just`-run all host tests; lint/mypy clean. **Approve before Wave B.**

## Wave B — firmware draw ops

- [ ] B1. `render.h`: `render_cells()` (paint bg then glyphs for a cell run).
- [ ] B2. `render.h`: `render_scroll()` (row-band blit + fill vacated rows).
- [ ] B3. `render.h`: `render_image()` (blit a chunk of RGB565 rows for the splash).
- [ ] B4. `main.cpp` dispatch: handle `DRAW_CELLS` / `SCROLL` / `DRAW_IMAGE`.
- [ ] B5. [MANUAL] build (`uvx --from platformio pio run`) + flash (gated: backup first) + visual check.
- [ ] B6. CHECKPOINT. **Approve before Wave C.**

## Wave C — bridge daemon

- [ ] C0. Programmer-side: a `just splash` recipe converts `terminal.splash.image`
      -> `terminal.splash.rgb565` (Pillow, resized to 320x240) ONCE, committed/synced.
- [ ] C1a. `pi/terminal/splash.py`: read the pre-converted `.rgb565` blob (no Pillow
      on the Pi) and send it as `DRAW_IMAGE` chunks; show during boot.
- [ ] C1b. `pi/terminal/login.py`: login screen — list `terminal.login.users`,
      CardKB user select, masked password entry (echo `*`), authenticate via PAM (`simplepam`); return the chosen user on success.
    - [ ]* C1bt. unit tests for the masked-entry state machine + auth adapter (mocked).
- [ ] C1. `pi/terminal/bridge.py`: show splash -> login -> spawn the shell as the
      chosen user on a PTY (the chosen user), spawn `bash -l` on a PTY (`pty.openpty`/`os.fork`
      or `pty.spawn`-style), set `TIOCSWINSZ` from geometry; pump PTY->vt->grid->diff->serial;
      pump CardKB `robust_keys`->PTY stdin. On PTY EOF / `logout`: clear and return
      to the LOGIN screen (never auto-respawn root). Robustness: reopen serial on
      error (bounded backoff), periodic full-repaint keyframe; login is the safe idle.
- [ ] C2. `pi/terminal/daemon.py`: load `terminal:` config from `.whiskerframe.yaml`,
      run the bridge; stdout/stderr logging; tracepoints (`terminal.*`).
- [ ] C3. runtime resize: a CardKB control chord adjusts `font_size`, recomputes
      geometry, `TIOCSWINSZ`, clear + full repaint.
- [ ] C4. `terminal.service` (Restart=always, hardened, DeviceAllow i2c-0 + the
      CYD serial) + idempotent `install.sh`.
- [ ] C5. `terminal:` block in `.whiskerframe.yaml` + `.whiskerframe.example.yaml`
      (font_size, a11y theme, serial port, keyframe interval, login users, splash
      image) — DONE in design phase; verify loader reads it. Save the a11y VS Code
      theme to `assets/themes/piiiiink-a11y.json`.
- [ ] C6. [MANUAL] deploy + install on Pi; type on CardKB; confirm bash echoes on CYD.
- [ ] C7. CHECKPOINT: docs (debug.md terminal section, manual-hardware-steps
      Section F), changelog, ai-decisions. **Final approval.**

## Notes

- Serial port + CardKB bus/addr come from `.whiskerframe.yaml` (reproducible-build).
- Daemon never crashes the loop; systemd Restart=always (field-robustness).
- Full redraw only on start / serial reopen / periodic keyframe; keystrokes are
  incremental cell/scroll ops (bandwidth).
- Credits: Waves A/B/C each gated by your approval; I build directly, minimal
  subagent use.
