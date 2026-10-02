# AI Engineering Decisions (Unreleased)

This document records the rationale for technical, architectural, and design
decisions made by the AI agent. Entries are append-only within the unreleased
cycle and are promoted on release.

## Packaging: rename distribution to `whiskerframe`

### Context

The prior `pyproject.toml` declared `[project].name = "src"` and configured
package discovery via `tool.setuptools.packages.find.include =
["imagesmacker*", "imagesmacker.models*"]`. Neither identifier corresponds to
the real source directory, which is `whiskerframe/`. Consequently the build
targeted a non-existent package: setuptools discovery matched no modules, and
the distribution name (`src`) was both non-descriptive and inconsistent with
the source tree.

### Decision

1. Set `[project].name = "whiskerframe"`, aligning the distribution name with
   the `whiskerframe/` source directory (Req 13.1).
2. Replace discovery `include` globs with `["whiskerframe*"]`, so setuptools
   finds the `whiskerframe` package and its subpackages, and a build includes
   the real source tree (Req 13.2, 13.3).
3. Retain `requires-python = ">=3.12"` (Req 12.1) and the existing ruff, black,
   and mypy `strict = true` configuration unchanged (Req 12.2).

### Optional dependency extras

Pillow and pyserial are declared as optional-dependency extras rather than core
dependencies:

- `preview = ["pillow>=10"]` — required only by the host-side `Preview_Renderer`.
- `serial = ["pyserial>=3.5"]` — required only by the serial transport.

This keeps the pure `Command_Builder` command path installable in minimal
environments without imaging or serial libraries present, satisfying Req 4.3.
The renderer and transport modules guard these imports lazily, so importing the
package or the builder never pulls in either extra.

### Artifact cleanup

Stale build metadata directories `src.egg-info` and `imagesmacker.egg-info`
were removed. They reflected the previous, incorrect packaging configuration
and would otherwise shadow or misrepresent the corrected distribution metadata
(per the `delete-temp-files` rule).

### Consequences

- The uv lockfile was resynchronized to reflect the renamed project.
- No public runtime API changed; the change is confined to build/packaging
  metadata. It is recorded under `Changed` in the changelog as a
  backward-compatible packaging correction.

## Firmware: CRC-8/SMBUS and length-prefixed framing in `frame.h`

### Context

The CYD firmware receives high-level drawing commands over a noisy USB-serial
link and must detect complete frames, validate integrity, and recover after
corruption (Req 1.2, 1.4, 2.1). The host `whiskerframe.protocol` module (task
6.1) serializes the same wire format, so the firmware decoder and host encoder
must agree exactly on framing and the integrity check.

### Decision

1. **Length-prefixed framing.** Each frame is
   `[SOF 0xA5][LEN uint16 LE][OPCODE][PAYLOAD][CRC8]`, where `LEN` counts
   `OPCODE + PAYLOAD`. The explicit length lets the decoder know when a command
   is complete before parsing; the `SOF` marker enables resynchronization.
2. **CRC-8/SMBUS as the integrity check.** Chose the standard CRC-8/SMBUS
   parameters — polynomial `0x07`, init `0x00`, no input/output reflection, no
   final XOR (check value `0xF4` over `"123456789"`) — computed over
   `OPCODE + PAYLOAD`. A non-reflected, zero-init/zero-xor variant is the
   simplest to implement identically in both C++ and Python, minimizing the
   chance of a host/firmware mismatch. The exact parameters and a reference
   Python implementation are documented inline in `frame.h` so task 6.1 can
   match it bit-for-bit.
3. **Discard-and-resync recovery (Req 1.4).** `FrameDecoder` is a byte-at-a-time
   state machine (HuntSOF → ReadLen → ReadBody → Validate). On a bad CRC, an
   unknown opcode, or a `LEN` exceeding the buffer cap, the in-progress frame is
   discarded and the decoder returns to hunting for the next `SOF`, so
   subsequent frames still process.
4. **~2 KB `LEN` cap.** A fixed `kMaxFrameLen = 2048` bounds the static receive
   buffer on the ESP32 and rejects runaway/garbage lengths, avoiding unbounded
   allocation on a constrained device. This comfortably exceeds any realistic
   `DRAW_TEXT`/`DRAW_RECT` payload.

### Consequences

- `frame.h` is header-only and hardware-independent, so the decoder logic is
  compilable and testable on the host (the decoder-recovery property test, task
  15.2, models the same state machine).
- The CRC contract is now pinned: any change to the polynomial or framing must
  be mirrored in `whiskerframe.protocol` or frames will fail validation on the
  device.

## Tooling: pure diff separated from OS enumeration in `device_discovery`

### Context

The `Device_Discovery` workflow (Req 5.1-5.4) must enumerate USB and serial
devices from the operating system, then diff the current set against a
`Baseline` to determine which serial node is the newly connected CYD and which
is the Pi's built-in serial. Enumeration is inherently impure (shelling out to
`lsusb`, globbing `/dev`), yet the diff logic is the part that carries the
correctness guarantee (Property 9) and must be unit- and property-testable
without physically connected hardware.

### Decision

1. **Two-layer split.** OS enumeration (`enumerate_devices`,
   `capture_baseline`, and the `_run_lsusb` / `_glob_tty` / `_glob_by_id`
   helpers) is isolated from the pure diff/report layer (`diff_devices`,
   `report`, `_preferred_ports`). The pure layer accepts and returns plain
   `DeviceSnapshot` values and never touches the OS, so the device-diff property
   test (task 16.2, Property 9) exercises `diff_devices` directly against
   synthetic snapshots.
2. **`frozenset` snapshot fields.** `DeviceSnapshot` stores each of the three
   enumeration sources (`usb`, `tty`, `by_id`) as a `frozenset`, making
   snapshots hashable and the diff a straightforward, order-independent set
   difference: `added = current - baseline`, `removed = baseline - current`.
3. **Three sources kept independent.** Rather than flattening all devices into
   one set, the snapshot preserves `lsusb`, `tty`, and `by-id` separately. This
   lets the report prefer the reboot-stable `/dev/serial/by-id/` symlinks while
   still diffing like-with-like per source.
4. **Prefer `by-id` symlinks in the report.** `_preferred_ports` returns the
   `by-id` symlinks when present and falls back to raw `tty` node paths only
   when no symlink exists, because `/dev/ttyUSB*` / `/dev/ttyACM*` numbers may be
   reassigned by the kernel across reboots whereas `by-id` paths are stable
   (Req 5.4).
5. **Baseline validity as an input constraint.** Per the Req 5.2 analysis, the
   baseline-captured-with-nothing-connected rule is a validity constraint on the
   snapshot passed to the diff, not a capture step the module enforces.
   `capture_baseline` documents the precondition but does not verify it, leaving
   the operator responsible for capturing while the CYD is unplugged.
6. **Graceful `lsusb` degradation.** `_run_lsusb` returns an empty set on a
   missing binary or non-zero exit rather than raising, so serial-node
   enumeration (the part that actually identifies the CYD port) still succeeds
   on hosts without `lsusb`.

### Consequences

- The correctness-bearing logic is hardware-free and deterministic, so
  Property 9 is verifiable in CI without a connected CYD; the manual operator
  run (task 16.3) only exercises the thin enumeration layer.
- Any future change to enumeration sources must extend `DeviceSnapshot` and the
  three-way diff in `diff_devices` together to keep the sources aligned.

## Tooling: Pi environment check split into a pure and an SSH layer

### Context

The Pi_Host connectivity workflow must connect over SSH and verify that
`python3`, `pip`, and `pyserial` are present (Req 6.1, 6.2), then report exactly
the absent components without halting on any single missing one (Req 6.3,
Property 10). The reporting logic is the part with interesting behavior and the
part the property test (task 17.2) targets, but SSH and a reachable Pi are not
available in an automated run.

### Decision

1. **Pure reporting layer, isolated from I/O.** `missing_components` and
   `format_report` in `scripts/pi_env_check.py` take a `ComponentPresence` value
   (three booleans) and return the absent component names plus a summary. They
   perform no I/O, so the property test exercises them directly with no network,
   no SSH client, and no Pi. This mirrors the pure/impure split already used for
   the device-discovery and flash-gate tooling.
2. **Report exactly the absent components; never halt (Req 6.3).** The pure layer
   always returns a complete `EnvReport` listing every absent component in the
   canonical `COMPONENTS` order. A single missing component is reported by name
   and the flow continues; one absent component is never treated as a broader
   halt. When SSH itself fails or times out, `probe_pi_environment` marks every
   probe absent so the pure layer still yields a full, well-formed report.
3. **Read-only probes only.** The three probes — `python3 --version`,
   `pip --version`, and `python3 -c "import serial"` — only read state; none
   installs, upgrades, or modifies anything on the Pi.
4. **SSH key referenced by path only.** `ssh_run` passes the private key to
   `ssh` via `-i <path>`; the module never opens, reads, or logs the key's
   contents. The default path `/home/lyra/.ssh/id_rsa` is a module constant.
5. **No shell, argument-vector invocation.** The remote command is passed to
   `subprocess.run` as an argument vector with `BatchMode=yes` (no interactive
   prompts) and a bounded `ConnectTimeout`/`timeout`, avoiding shell
   interpretation of any value.

### Consequences

- The reporting behavior (Property 10) is verifiable in CI without hardware; only
  the thin SSH layer requires a reachable Pi (the manual task 17.3).
- The key-by-path contract keeps private-key material out of process memory and
  logs.
- The check makes no changes to the Pi, so it is safe to run repeatedly during
  environment bring-up.

## Flash safety gate: pure `gate_decision` guarding an irreversible write

### Context

Flashing the CYD is irreversible — a write overwrites the factory firmware
(Req 7). The write must be gated on three independent preconditions: a validated
`Flash_Backup` exists (Req 7.4, 7.6), every esptool operation carries an explicit
valid flash size rather than `ALL`/unspecified/invalid (Req 7.2), and the operator
explicitly confirmed the write (Req 7.5). This decision carries the correctness
guarantee for the whole gate (Property 8) and must be verifiable without touching
hardware or firing esptool.

### Decision

1. **Pure decision, isolated from esptool.** `gate_decision` takes the
   `BackupValidation` from `validate_backup`, the explicit size, and the
   confirmation flag, and returns a `GateDecision`. It invokes no esptool, accesses
   no flash, and has no side effects, so Property 8 is exercised directly against
   synthetic inputs. This mirrors the pure/impure split used across the tooling
   scripts.
2. **Permit IFF all three preconditions hold; default to BLOCK.** `permitted` is
   `True` only when the backup is valid AND the size is an explicit positive `int`
   AND the operator confirmed. Every other state blocks. Because this gates an
   irreversible action, the default and every unknown/edge case resolve to BLOCK.
3. **`bool` is not a valid size.** Although `bool` subclasses `int`, a size of
   `True`/`False` is rejected alongside `None`, non-`int`, `0`, and negatives, so
   only a genuine positive byte count (e.g. `0x400000`) satisfies Req 7.2.
4. **Authoritative boolean, advisory diagnostics.** `permitted` is the single
   signal a caller may gate on. `reasons` (a `BlockReason` tuple), `detail`, and the
   echoed inputs explain *why* a write was blocked but are deliberately incapable of
   overriding `permitted`; the frozen dataclass prevents post-hoc mutation.

### Consequences

- The write-permit logic (Property 8) is verifiable in CI with no CYD attached; the
  manual esptool read/write steps consume this decision but cannot bypass it.
- Any future precondition must be added as a new `BlockReason` and folded into the
  conjunction in `gate_decision`, keeping BLOCK as the default posture.
- Callers must branch solely on `GateDecision.permitted`; treating any diagnostic
  field as permission would reintroduce the irreversible-write risk this gate exists
  to remove.

## Firmware: DRAW_TEXT / DRAW_RECT rendering and bounds-skip in `render.h`

### Context

The CYD firmware must render two drawing commands on the ILI9341 via TFT_eSPI:
`DRAW_TEXT` at a resolved anchor with optional multiline layout (Req 2.3) and
`DRAW_RECT` as a filled or outline rectangle (Req 2.4). Req 2.5 additionally
requires that a `DRAW_TEXT` whose anchor/coordinates would fall outside the
visible display, or whose parameters are invalid, be skipped ENTIRELY — with no
clipping and no placement adjustment. `render.h` decodes the payloads produced
by the host `whiskerframe.protocol` module and already validated by the
`frame.h` frame layer, then draws them.

### Decision

1. **Runtime bounds, not compile-time macros.** The on-screen bounds check
   (`point_in_bounds`) uses `tft.width()` / `tft.height()` rather than the
   `TFT_WIDTH` / `TFT_HEIGHT` build flags in `platformio.ini`. Those macros
   describe the panel in its native, unrotated orientation (240x320); after the
   `setRotation` call in `setup()` (task 15.5) the visible extent may be
   swapped (320x240). Querying the runtime extent keeps the Req 2.5 bounds check
   correct under any rotation.

2. **Bounds-skip is distinct from frame discard (Req 2.5).** `frame.h` already
   discards unparseable frames (bad CRC / unknown opcode / oversized LEN) and
   resynchronizes. `render.h` operates only on frames the frame layer accepted,
   so its skip logic is a separate, payload-level decision: on a malformed
   payload (shorter than the fixed header, or `text_len` overrunning the
   received bytes), an out-of-range packed anchor nibble, or any anchor point
   off-screen, `render_text` returns without drawing anything. The frame is
   still consumed normally by the caller; only the draw is declined. No pixel is
   clipped or repositioned.

3. **Validate every multiline row before drawing.** For multiline text, each
   LF-separated line has its own anchor point at `y + line_h * row`. All row
   anchor points are checked against the display bounds up front; if any is
   off-screen the whole command is skipped, so a multiline block is never
   partially drawn. This keeps the "skip entirely" contract atomic for the
   command rather than per-line.

4. **Anchor byte -> TFT_eSPI datum via a 3x3 grid.** `anchor_to_datum` maps the
   packed anchor (high nibble `h` in {0=l,1=m,2=r}, low nibble `v` in
   {0=t,1=m,2=b}) onto the nine TFT_eSPI text datums through a static
   `[h][v]` table, preserving the imagesmacker `[lmr][tmb]` alignment semantics
   on-device. Out-of-range nibbles return false and cause the command to be
   skipped (Req 2.5).

5. **Inverted flag swaps fg/bg at draw time.** The host resolves multiline line
   order; the firmware honors the `inverted` flag only by swapping the
   foreground and background colors passed to `setTextColor`, drawing text as
   bg-on-fg. Line-order reversal for inverted multiline is a host-side
   (`Command_Builder`) concern, matching the design's split of placement math to
   the host.

6. **Bounded stack buffer for C-string conversion.** `TFT_eSPI::drawString`
   needs a NUL-terminated `char*`. Text segments are copied into a stack buffer
   sized to `kMaxFrameLen` (the same 2 KB cap enforced by `frame.h`), so the
   copy can never exceed the largest payload the frame layer would have
   accepted; lengths are clamped to `kMaxFrameLen - 1` defensively.

7. **Rectangles rely on native clipping (Req 2.4).** Req 2.5's skip-entirely
   contract applies to `DRAW_TEXT` only. `render_rect` therefore draws directly
   with `fillRect` / `drawRect`, letting TFT_eSPI clip any off-screen pixels
   natively; it only guards against a payload shorter than the fixed 11-byte
   layout.

### Verification

`render.h` depends on the `TFT_eSPI` Arduino library and cannot be compiled in
this environment without the ESP32/Arduino toolchain, so it was reviewed by
inspection against the design "Payload encodings" and the `frame.h` decoder
contract rather than compiled. On-device verification is deferred to the
firmware bring-up on connected hardware (tasks 15.5, 19-20).

### Consequences

- The payload byte offsets in `render.h` are pinned to the design encoding and
  must move in lockstep with the host `whiskerframe.protocol` serializer
  (task 6.1); a divergence would misdecode fields silently.
- `render.h` is header-only and hardware-coupled through `TFT_eSPI`; its logic
  (anchor->datum mapping, bounds skip) is simple enough to review statically but
  is not exercised by the host-side property tests.

## Firmware: `main.cpp` boot/dispatch loop for the CYD sketch

### Context

`frame.h` (decoder) and `render.h` (TFT_eSPI renderers) are header-only and
hardware-free/hardware-coupled respectively; the sketch still needs an Arduino
entry point that wires them to the display and the serial link (design "Module
sketch", Req 2.2, 1.2, 2.1). `main.cpp` owns the global `TFT_eSPI` instance and
`FrameDecoder`, initializes the panel, and runs the receive/dispatch loop.

### Decision

1. **Landscape rotation 1.** The CYD panel is natively 240x320 portrait
   (`TFT_WIDTH`/`TFT_HEIGHT` build flags). `setup()` calls
   `tft.setRotation(1)` to present the usual CYD landscape orientation
   (320x240). This is deliberately consistent with `render.h`, which checks the
   Req 2.5 bounds against the runtime `tft.width()`/`tft.height()` (post-rotation
   extent) rather than the compile-time macros, so the bounds contract holds
   under the chosen rotation.
2. **115200 baud, single source of truth.** `Serial.begin(115200)` matches
   `monitor_speed` in `platformio.ini` and the host transport (Req 2.2). The
   value is a named `kSerialBaud` constant so the sketch and the PlatformIO
   monitor cannot silently drift apart.
3. **Drain the whole RX buffer per `loop()`.** `loop()` reads every currently
   available byte through `decoder.feed()` in a `while (Serial.available())`
   loop, dispatching each frame the decoder completes, then returns. This keeps
   latency low (a burst of queued bytes is consumed in one pass) without
   blocking on bytes that have not arrived yet. A defensive `Serial.read() < 0`
   guard breaks the loop if `available()` and `read()` ever disagree.
4. **Dispatch only the required opcodes.** `dispatch()` routes `DRAW_TEXT` ->
   `render_text` and `DRAW_RECT` -> `render_rect` (Req 1.3, 2.1); the reserved
   `CLEAR`/`FLUSH` opcodes the frame layer accepts are an intentional no-op here
   since they are outside the required render surface. Frame-level recovery (bad
   CRC / unknown opcode / oversized LEN) is already handled inside
   `FrameDecoder` (Req 1.4), so `main.cpp` never sees an invalid frame.

### Verification

`main.cpp` depends on the ESP32 Arduino core and `TFT_eSPI` and cannot be
compiled in this environment (no ESP32/Arduino/TFT_eSPI toolchain). It was
reviewed by inspection against the `frame.h` decoder API (`feed`, `opcode`,
`payload`, `payload_len`) and the `render.h` renderer signatures
(`render_text`/`render_rect(TFT_eSPI&, const uint8_t*, uint16_t)`), and the baud
against `platformio.ini`. On-device verification is deferred to firmware
bring-up on connected hardware (tasks 19-20).

### Consequences

- The rotation choice couples `main.cpp` and `render.h`: because bounds are
  checked at runtime, changing `kDisplayRotation` automatically keeps the Req
  2.5 skip contract correct with no code change in `render.h`.
- The sketch is now compilable in place (`src_dir = .`) once the toolchain is
  available; `frame.h` + `render.h` + `main.cpp` form the complete firmware.

## Preview: guarded Pillow renderer reusing builder placement in `preview.py`

### Context

The optional `Preview_Renderer` must render a host-side image of drawing
commands (Req 4.1) that mirrors the imagesmacker 7.0.0 anchor/coordinate/
multiline model (Req 4.2) and matches the placement the device receives
(Property 6, Req 8.4). Pillow is an optional `preview` extra: importing the
package or the `Command_Builder` must never require it, and a preview call
without Pillow must fail with a clear, actionable error (Req 4.4).

### Decision

1. **Render resolved commands, not raw geometry.** `PreviewRenderer.render`
   consumes the same resolved `DrawText`/`DrawRect` models the
   `Command_Builder` produces. Each command already carries the anchor pixel
   `(x, y)` that `RectangleCoordinates.anchor_coordinates` computed, so the
   preview reuses the builder's placement rather than resolving anchors a second
   time. This makes preview/device parity structural (Property 6): the preview
   cannot drift from the builder because it starts from the builder's output.
2. **Reuse the shared metrics table for multiline stacking.** Line widths and
   the glyph cell height come from `whiskerframe.metrics` (the same table the
   builder uses), and multiline lines stack by the command's own `line_h`.
   `_line_origin` reproduces the on-device block-anchor placement with the same
   pure integer floor-division used in `coordinates.py`/`metrics.py`, so no
   alternate anchor math is introduced.
3. **Lazy, guarded Pillow import (Req 4.4).** `PIL` is never imported at module
   top level; a `_require_pillow` helper imports it inside `render` and raises a
   `RuntimeError` naming the `preview` extra when it is missing. Importing
   `whiskerframe.preview` therefore succeeds without Pillow, the package
   `__init__` does not import `preview` at all, and `Command_Builder` stays fully
   operable in a Pillow-free environment.
4. **RGB565 -> RGB888 by bit replication.** `rgb565_to_rgb888` expands the packed
   5-6-5 channels by replicating high bits into the low bits, matching how the
   ILI9341 presents RGB565, so preview colors stay visually consistent with the
   device.

### Consequences

- Preview parity is verified by asserting the builder-resolved `(x, y)` is the
  block anchor the preview places (Property 6); the renderer holds no
  independent anchor logic that could diverge.
- `preview.py` is the only host module that touches Pillow, keeping the pure
  command path free of an imaging dependency (Req 4.3).

## Property tests for `scripts/` importing across the package boundary

### Context
Property 9 (`Device_Discovery` diff) and Property 10 (Pi_Host environment-check
reporting) validate pure logic that lives under `scripts/` (`device_discovery`,
`pi_env_check`), not under the packaged `whiskerframe/` tree. The runnable test
scripts live under `test/`, are executed directly via
`uv run python test/<file>.py` (not pytest), and must import the
`scripts/`-resident modules under test. `scripts/` is not on `sys.path` when a
file under `test/` is run directly, and `whiskerframe` packaging excludes
`scripts/` (`[tool.setuptools.packages.find] include = ["whiskerframe*"]`), so a
plain `import device_discovery` fails.

### Decision
1. **Resolve `scripts/` at runtime via `sys.path`, not packaging.** Each
   property test prepends the repository's `scripts/` directory to `sys.path`
   using `Path(__file__).resolve().parent.parent / "scripts"` before importing
   the module under test. This keeps `scripts/` out of the shipped
   `whiskerframe` distribution while letting the direct-run test scripts import
   its pure functions. The `scripts/__init__.py` marker lets the modules import
   as top-level names (`import device_discovery`, `import pi_env_check`).
2. **Drive the pure layer only.** The tests call `diff_devices` and
   `missing_components`/`format_report` directly with hypothesis-generated
   inputs (device-id `frozenset`s; presence `bool`s). No OS enumeration, SSH, or
   network is touched, matching the modules' pure/side-effecting split, so the
   properties are checked deterministically and offline.
3. **Assert against the reference set arithmetic.** Property 9 asserts the diff
   equals per-source `current - baseline` (added) and `baseline - current`
   (removed); Property 10 asserts the missing list equals the absent components
   filtered in `COMPONENTS` order and that `all_present` holds iff the missing
   list is empty. The oracle is recomputed independently in the test rather than
   reusing the module's own derivation.

### Consequences
- The `import` after `sys.path.insert` is intentionally below the top of the
  module; ruff does not flag it under the project config (no `E402`/`RUF100`
  needed), and the pattern is contained to the two `scripts/`-targeting property
  tests.
- `scripts/` remains unpackaged; the tests stay runnable in-tree without adding
  `scripts` to the distribution or introducing a pytest dependency.


## Configuration: externalized to `.env` and `.whiskerframe.yaml`

### Context

Per the reproducible-build rule, scripts must not hard-code environment- or
hardware-specific values. `scripts/pi_env_check.py` previously hard-coded the Pi
host, user, SSH key path, venv path, and component list.

### Decision

1. Environment/deploy values (`PI_HOST`, `PI_USER`, `DEFAULT_KEY_PATH`,
   `DEFAULT_VENV_PATH`) live in `.env` (gitignored) with a committed
   `.env.example` template for new users. The justfile already loads `.env`
   (`set dotenv-load`).
2. Project and hardware facts (`components`, UPS/INA219 parameters, CYD serial
   port) live in the committed `.whiskerframe.yaml`.
3. `scripts/config.py` centralizes loading: `env()` reads `.env` with documented
   fallbacks, `load_yaml_config()` parses `.whiskerframe.yaml`. Both are optional
   at import so a fresh checkout still runs on defaults.
4. `python-dotenv` and `pyyaml` are dev dependencies (config lives with dev
   tooling, not the Pi runtime path).

### Consequences

- A new user copies `.env.example` to `.env`, edits four values, and the tooling
  targets their hardware without code edits -- reproducible by construction.
- Hardware facts (INA219 at `0x41`, 3S 9.0-12.6 V, CYD CH340 port) are recorded
  once in `.whiskerframe.yaml` and consumed everywhere.

## Battery monitor: userspace `power_supply` publisher and default-off auto-shutdown

### Context

The cyberdeck's UPS Module 3S carries a Texas Instruments INA219 on `/dev/i2c-1`
(`0x41`). The OS should see the pack as a battery, and a daemon should surface
its state of charge. Two forces shape the design: the daemon must run inside the
minimal uv-managed Pi venv (which ships only `pydantic`/`pyserial`, no `smbus`),
and it guards a physical power source where a wrong automated action (an
unwanted poweroff) is destructive and hard to reverse in the field.

### Decision

1. **Stdlib-only I2C driver.** `ina219.py` talks to the chip directly through the
   Linux i2c-dev character device (`os.open` + `fcntl.ioctl` with
   `I2C_SLAVE=0x0703`, 16-bit big-endian register reads/writes) rather than
   depending on `smbus`/`smbus2`. This keeps the Pi runtime declaration unchanged
   and the daemon installable in the existing venv. The device is read-only apart
   from the two one-time writes the INA219 requires (calibration `4096` and the
   config word), so the monitor cannot perturb the pack.

2. **Userspace `power_supply` mirror over an in-kernel `ina2xx` overlay.** The
   publisher writes the exact kernel `POWER_SUPPLY_*` `uevent` grammar (plus a
   `status.json`) under `/run/battery_monitor/`. The *more* kernel-native option
   — binding the mainline `ina2xx` hwmon driver via a device-tree overlay and a
   battery `power_supply` shim — needs a compatible kernel and a custom overlay
   (an `ina219@41` node on `i2c1`). The userspace mirror works on the stock image
   with no kernel rebuild, so it is the robust default for this exact board; the
   overlay path is documented in the README as the alternative. The two files are
   written atomically (temp + `fsync` + `os.replace`) so a reader never sees a
   torn `uevent`.

3. **`auto_shutdown` defaults to `false` (railguard).** At/below
   `critical_percent` the daemon always logs `CRITICAL`, but it only powers off
   when the operator explicitly sets `auto_shutdown: true` in `.whiskerframe.yaml`.
   An automatic poweroff is destructive, so the safe default is to warn and keep
   running; opting in is a deliberate configuration choice. Even when enabled, a
   failed `systemctl poweroff` is logged and swallowed so the daemon keeps
   publishing.

4. **Transient I2C errors never crash the loop.** Every I2C transaction raises the
   single typed `INA219Error`; the poll loop catches it, logs, and retries with a
   bounded exponential backoff (1 s → 30 s), resetting on the next good read. A
   watchdog/`Restart=on-failure` unit then covers only genuinely fatal states.

5. **Reproducible config, not hard-coding.** All hardware/behavioral values come
   from the `.whiskerframe.yaml` `ups:` block via `scripts/config.py`, with
   fallbacks matching the live-verified facts (INA219 `0x41`, 3S 9.0–12.6 V,
   `11.67 V → 74 %`). New daemon keys (`poll_interval_seconds`, `auto_shutdown`,
   `power_supply_name`) live in the same committed block.

### Verification

`ina219.py`'s register math (bus `(raw>>3)*0.004`, signed current `*0.1`), the
`battery.py` percent/status conversions, the `power_supply.py` `uevent`/`status`
output, and the `daemon.py` backoff-then-publish loop were exercised locally
against a fake in-memory I2C device (no real hardware required). `ruff`, `black`,
and `mypy` pass on `pi/battery_monitor`. On-device verification (real INA219
reads, systemd bring-up) is deferred to the Pi deployment; the orchestrator runs
`install.sh` there.

### Consequences

- The `uevent` key layout is pinned to the kernel `power_supply` grammar; any
  consumer expecting a real battery reads it unchanged, and a later switch to the
  `ina2xx` overlay can drop the userspace mirror without changing the conversion
  layer.
- The daemon is safe to run continuously on the UPS: read-only I2C, no default
  poweroff, and no crash on bus glitches.


## Config: per-user live file + committed example (`.whiskerframe.yaml`)

### Decision

`.whiskerframe.yaml` is treated like `.env`: the live file is **gitignored**
(per-user), and `.whiskerframe.example.yaml` is the **committed** template. The
dev's live config equals the example, but gitignoring the live file means a user
who clones the repo keeps their own config across updates — a repo pull cannot
clobber local hardware settings. `scripts/config.py` loads the live file and
falls back to the example when it is absent, so a fresh clone works before the
user copies it.

## CYD terminal: a11y palette, login gate, splash

### Decision

1. **Accessibility.** The piiiiink palette was audited for WCAG contrast on the
   blurple terminal background `#191a28`. The main colours already passed, but the
   ANSI terminal set (`ansiBlack`/`ansiBlue`/`ansiRed`) and the alpha-faded
   `editor.foreground` failed; all were corrected to >= 4.5:1 while keeping the
   piiiiink hue family. The corrected set is the terminal theme (RGB565 in config)
   and a saved VS Code theme (`assets/themes/piiiiink-a11y.json`).
2. **Login gate (supersedes the earlier boot-to-root note).** The CYD terminal no
   longer boots straight to root. A splash image shows during boot, then a login
   screen lets the user pick a configured user and enter a password echoed only as
   asterisks; authentication is real system auth (PAM/`su`), not a bespoke
   comparison. `logout` (or shell EOF) returns to the login screen, never an
   unauthenticated root prompt — which is also the safe idle state for the
   field-robustness rule.
3. **Splash** is a config-pointed image, converted host-side to RGB565 and blitted
   via a new `DRAW_IMAGE` op.

## Firmware (Wave B): DRAW_CELLS / SCROLL / DRAW_IMAGE in `render.h`

### Context

The `cyd-terminal` feature adds three incremental draw ops over the existing
`DRAW_TEXT`/`DRAW_RECT` surface so a keystroke never triggers a full-screen
redraw at 115200 baud: `DRAW_CELLS` (`0x03`, a run of fixed-cell glyphs),
`SCROLL` (`0x04`, shift a row band), and `DRAW_IMAGE` (`0x05`, a raw RGB565
block for the boot splash). The firmware decode MUST match the host
`whiskerframe.protocol` wire layouts byte-for-byte: `_DRAW_CELLS_HEADER =
"<HHHHBH"`, `_SCROLL = "<bHHH"`, `_DRAW_IMAGE_HEADER = "<HHHH"`.

### Decision

1. **Fixed-cell geometry from font_size, pinned to `metrics.py`.** `render_cells`
   computes `cell_w = 6*font_size`, `cell_h = 8*font_size` (font_size 0 treated
   as 1), matching `whiskerframe/metrics.py` `FONT_METRICS` and the TFT_eSPI 6x8
   built-in font that `setTextSize(N)` scales linearly. It paints the whole run
   background in one `fillRect` first (clean overwrites), then draws each glyph in
   `fg` at a top-left datum. Cells past the right edge are skipped per-cell and a
   run that starts off the right/bottom edge is skipped; a short/malformed payload
   (header missing or `len` overrunning the received bytes) is skipped entirely,
   matching the `render_text` skip contract rather than clipping mid-glyph.

2. **SCROLL cell-height tracking (the key self-containment decision).** `SCROLL`
   carries its `top`/`bottom` band in CELL units but has NO `font_size` field, so
   the firmware cannot derive a cell's pixel height from the SCROLL payload alone.
   Rather than reinterpret the band as pixels (which would contradict the design's
   cell-unit contract), the firmware tracks the cell height of the most recent
   `DRAW_CELLS` in a file-scope static (`active_cell_height()`, default 8 px =
   size 1) and uses it to convert SCROLL's cell band to the pixel band
   `[top*cell_h, (bottom+1)*cell_h)`. This is self-contained and correct for the
   terminal data flow: the host paints cells at the active font before scrolling,
   so the tracked height always matches the band the host intends.
   Trade-off: a `SCROLL` arriving before any `DRAW_CELLS` scrolls assuming an 8 px
   cell. In the actual flow the splash/login/terminal paint cells first, so this
   never happens in practice; it degrades to a size-1 scroll rather than failing.

3. **Pixel-band scroll via bounded scanline `readRect`/`pushRect`.** The band is
   clamped to the visible display, then shifted up (`rows > 0`) or down
   (`rows < 0`) by `abs(rows)*cell_h` pixels, copying one scanline at a time into a
   single file-scope 320-wide `uint16_t` buffer (`kScrollMaxWidth`) and filling the
   vacated rows with `fill`. Copy direction is chosen so sources are read before
   being overwritten (top-down for up-scroll, bottom-up for down-scroll). A zero
   shift, an invalid band (`bottom < top`), or a shift that clears the whole band
   degrades to a plain `fillRect` (or a no-op) — robust, never a partial/garbage
   blit. No heap: the one scanline buffer is file-scope `static`, bounded to the
   panel width.

4. **DRAW_IMAGE endianness: native/little-endian RGB565, blit in place.** The
   `data` bytes are interpreted as native-endian `uint16` and blitted straight
   from the payload pointer with `tft.pushImage(x, y, w, h, (const uint16_t*)data)`
   — no copy, no allocation. TFT_eSPI `pushImage` expects pixels in the panel's
   native `uint16` order, and `whiskerframe.terminal.DrawImage.data` is raw
   caller-supplied bytes, so the host-side splash converter MUST emit
   little-endian/native-endian RGB565 to match. (If a future converter emits
   big-endian, it must byte-swap or set the TFT_eSPI swap flag; the chosen contract
   is native/little-endian to avoid a per-pixel swap on-device.) The payload length
   is validated to equal `header(8) + w*h*2` and a short payload is skipped, so a
   truncated frame never blits past the receive buffer. Off-screen pixels rely on
   TFT_eSPI's native clipping (parallels `render_rect`), so no bounds-skip is
   applied.

5. **No dynamic allocation on the constrained ESP32.** `DRAW_CELLS` draws one
   glyph at a time from a 2-byte stack buffer; `DRAW_IMAGE` blits in place; `SCROLL`
   uses the single bounded file-scope scanline buffer. This keeps RAM use flat
   (measured 7.5% of 320 KB after the build) regardless of payload size.

### Verification

Compiled clean with the real toolchain in this environment via
`uvx --from platformio pio run` (esp32dev, TFT_eSPI 2.5.43): `[SUCCESS]`, only
the unrelated `TOUCH_CS pin not defined` TFT_eSPI warning. RAM 7.5% / Flash
22.9%. The byte offsets were cross-checked against `whiskerframe/protocol.py`'s
`struct` formats (`<HHHHBH` / `<bHHH` / `<HHHH`). On-device visual verification
(real cell runs, scroll bands, splash blit) is deferred to the gated [MANUAL]
flash + bring-up; this agent did NOT flash.

### Consequences

- The `render.h` byte offsets are pinned to the host serializer; a change to any
  of the three `struct` formats in `protocol.py` must move in lockstep here.
- `active_cell_height()` couples `render_scroll` to the most recent
  `render_cells`; if the terminal ever interleaves two font sizes within one
  scroll region, the host must re-send cells rather than relying on a stale
  tracked height. Documented so a future caller does not assume per-SCROLL font
  independence.
- The DRAW_IMAGE native-endian contract is now pinned: the splash `.rgb565`
  converter is the single place that must honor it.

## CYD terminal Wave C: `su`-based shell, root service, resize chord, splash chunking

### Context

Wave C turns the pure host core (Wave A) and firmware draw ops (Wave B) into a
live Pi daemon: a boot splash, a login gate, and a real `bash -l` login shell
rendered on the CYD and typed on the CardKB. Several design decisions have
security and robustness consequences and are recorded here.

### Decision: start the shell via `su - <user>` on a forked PTY

The bridge authenticates the user via PAM (`simplepam`) at the login gate, then
starts the session with `pty.fork()` and `execvp("su", ["su", "-", user])` in the
child.

- **Rationale.** `su - <user>` is a PAM-aware system binary that establishes the
  full target context — uid/gid, supplementary groups, `$HOME`, `$SHELL`, a login
  environment, and a PAM session — which a bare `os.setuid` + `exec` would not
  reproduce correctly. Delegating to `su` keeps the privilege transition in a
  well-audited system component rather than hand-rolling credential handling in
  the daemon. The user is already authenticated before `su` runs; `su` re-enters
  PAM but the design treats the gate's PAM check as the authoritative boundary.
- **Consequence.** The daemon process must run as root so `su` can switch to any
  configured account (including unprivileged users and root itself). This is why
  the service runs as root and `NoNewPrivileges` is disabled (see below).
- **Alternatives rejected.** `os.setuid`/`setgid` + manual env setup is fragile
  (easy to leak the parent environment or miss group membership and PAM session
  setup). A restricted/custom shell was rejected per the design: the deck wants a
  genuine console, and the daemon is a transport, not a sandbox.

### Decision: run the systemd service as root with `NoNewPrivileges=false`

Unlike `battery-monitor.service` (which drops to a hardened least-privilege
profile), `terminal.service` runs as root and explicitly sets
`NoNewPrivileges=false`.

- **Rationale.** The service's whole purpose is to `su` into other users on
  demand after a password check. `su` relies on being able to gain privileges
  (setuid), which `NoNewPrivileges=yes` forbids; and switching to an arbitrary
  configured user requires starting as root. The **security boundary is the login
  gate**, not the service user: nothing runs an unauthenticated shell, so physical
  access to the deck no longer yields a free root console (a change from the
  earlier "boots to root" posture). Password input is masked and never logged.
- **Consequence / least privilege retained where possible.** The unit still scopes
  device access with `DeviceAllow` to only the CYD serial and `/dev/i2c-0` (the
  CardKB bus); it does not grant blanket device access. The broader hardening
  directives used by the battery daemon (`ProtectSystem=strict`, `ProtectHome`,
  `PrivateTmp`, namespace/realtime restrictions) are intentionally omitted because
  they would break `su`/PAM and the login shells' expectations of real home
  directories and a normal filesystem view.

### Decision: resize chord is `Ctrl+]` (`0x1d`), ignored during login

Runtime font-size resize cycles sizes 1/2/3 when the CardKB sends `0x1d`
(`Ctrl+]`, ASCII GS).

- **Rationale.** The chord must be a byte that is essentially never wanted inside
  an interactive shell, so intercepting it costs no normal functionality.
  `Ctrl+]` is the classic telnet escape, not a shell line-editing key (unlike
  `Ctrl+A`/`Ctrl+E`/`Ctrl+R`/`Tab`, which readline uses heavily), making it a safe
  sacrifice. On the resize it recomputes `TerminalGeometry`, rebuilds the grid and
  emulator, pushes the new window size to the PTY via `TIOCSWINSZ` (so programs
  reflow), and forces a full repaint.
- **Login handling.** The chord is ignored on the login screen so it can never
  disturb user selection or password entry; resize is a shell-only affordance.

### Decision: splash sent as 2-row `DRAW_IMAGE` chunks

`show_splash` streams the 153600-byte RGB565 blob as 120 `DRAW_IMAGE` frames of
two panel rows each (320x2 px -> 1280-byte payload).

- **Rationale.** A whole-frame `DRAW_IMAGE` payload (153600 bytes) vastly exceeds
  the firmware's ~2 KB frame cap. Two rows per chunk yields a 1280-byte payload,
  comfortably under the cap while keeping the frame count modest (120). The blob
  is pre-converted on the programmer (Pillow) and little-endian RGB565 to match
  the firmware pixel contract, so the Pi never runs an imaging library at boot —
  it only reads bytes and frames them.
- **Robustness.** A missing, empty, or row-misaligned blob is skipped silently
  (the login screen is the safe idle state), and a serial write error aborts the
  splash without raising, so the splash is always safe on the boot path.

### Decision: incremental rendering via `grid.diff`, no explicit `SCROLL` emission

The bridge renders each frame by diffing the new grid against the previous
snapshot and sending the changed `DRAW_CELLS` runs; it does not try to detect a
line scroll and emit a dedicated `SCROLL` op.

- **Rationale.** Reliably inferring "this frame is the previous frame shifted up
  by one row" from a pure cell diff is error-prone (any content change on the
  scrolled rows defeats it), and a wrong `SCROLL` corrupts the display. The
  grid's `scroll_up` shifts cells in the model, so `diff` already emits exactly
  the cells that changed — correct by construction. This trades some serial
  bandwidth on a full-screen scroll for guaranteed correctness and simplicity,
  consistent with field-robustness (a simpler, never-wedging path beats a richer
  one that can mis-scroll). The firmware `SCROLL` op remains available for a
  future optimization but is not required for correctness.
