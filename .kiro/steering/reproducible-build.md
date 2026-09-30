---
inclusion: always
name: reproducible-build
description: Keep the cyberdeck build repeatable and reproducible; document every hardware and system setup step.
---

# Reproducible Cyberdeck Build

This cyberdeck (Raspberry Pi host + ESP32 CYD display + UPS module and any other
components) must be **repeatable and reproducible** from scratch. Treat every
hardware/software setup step as something another person -- or future-you on a
fresh board -- can replay from the docs alone, without guessing.

## Rules

- **Declare, don't improvise.** Pin every dependency and version (uv-managed
  `pyproject.toml` / lockfiles, PlatformIO `platformio.ini`, firmware pins/baud).
  Never rely on ad-hoc `pip install`, undeclared globals, or manual one-off state.
- **Document every physical + system step.** Any wiring, boot-config change
  (e.g. `dtparam=i2c_arm=on`), enabled interface, flashed firmware, installed
  daemon, or provisioning command MUST be captured in `docs/dev/manual-hardware-steps.md`
  (and the relevant `docs/` page) as an ordered, copy-pasteable procedure with
  expected output.
- **Make setup scriptable.** Prefer an idempotent script/recipe (e.g. `pi/bootstrap.sh`,
  a `just` target, a systemd unit installer) over prose-only instructions. Running
  it twice must be safe.
- **Record identifying facts.** Chip part numbers, I2C addresses, serial
  port paths (prefer stable `/dev/serial/by-id/...`), pin maps, and thresholds go
  in the docs, not just in code.
- **Verify reproducibility.** After a change, confirm the documented steps still
  produce the same result (or update them). When you cannot fully verify on
  hardware, state exactly what was and was not verified.
- **Back up before irreversible steps.** Firmware flashes and flash writes require
  a validated backup and the flash safety gate first (see the flash gate).
- Keep `docs/dev/changelog.md` and `docs/api/unreleased/ai-decisions.md` current so
  the *why* behind each setup decision is reproducible too.
