---
trigger: always_on
glob:
description:
---

# Field Robustness

This cyberdeck is deployed in the field. The user often CANNOT open the case,
reflash, or fix things on the go. Every on-device component (Pi daemons, I2C
readers, serial links, firmware) must be robust enough to run unattended for long
periods and recover on its own.

## Rules

- **Never crash the long-running path.** Daemons, poll loops, and readers must
  catch transient hardware errors (I2C `OSError`, serial glitches, short reads)
  and retry with bounded backoff rather than exiting. A single bad read must not
  take down the service.
- **Self-recover.** systemd units use `Restart=on-failure`/`always` with a
  `RestartSec`. Re-open a device after a bus error instead of assuming the fd is
  still valid. Resynchronize framed protocols after corruption.
- **Degrade, don't die.** If an optional peripheral (CardKB, UPS, display) is
  absent or stops responding, the rest of the system keeps working; log and keep
  going.
- **Watchdog where it matters.** Prefer heartbeats/liveness signals for critical
  loops so a hung peripheral is detected and the service restarts.
- **No interactive prompts on-device.** Nothing in the deployed path may block
  waiting for input, a passphrase, or a login shell (that caused real hangs).
- **Idempotent, reproducible setup.** Install/enable steps are re-runnable; config
  comes from `.whiskerframe.yaml` / `.env`, not hand-edits that cannot be replayed.
- **Fail safe on power.** Battery-critical handling must be deliberate and
  logged; irreversible actions (shutdown, flash) stay gated.
- **Test the unhappy path.** When adding a device driver, exercise device-absent,
  mid-read disconnect, and reconnect, not just the happy read.

Robustness outranks feature completeness: a simpler component that never bricks
the deck in the field beats a richer one that can wedge it.
