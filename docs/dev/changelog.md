<h1 align="center" style="font-weight: bold">
    Changelog
</h1>

This software uses [Semantic Versioning v2.0.0](https://semver.org/spec/v2.0.0.html). This changelog is based on [keepachangelog.com v1.1.0](https://keepachangelog.com/en/1.1.0/).

**Types of Changes**

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Removed` for now removed features.
- `Fixed` for any bug fixes.
- `Security` in case of vulnerabilities.

## 0.1.0 (Unreleased)

### Added

- `scripts/debug.py` and `pi/battery_monitor/debug.py` env-gated, stdlib-only tracepoint helpers (identical API: `DEBUG_ENV`, `is_debug`, `tracepoint`) that emit a single greppable `[TP] <name> key=value ...` line to `stderr` when `WHISKERFRAME_DEBUG` is truthy (`1`/`true`/`yes`, case-insensitive) and are near-zero-cost no-ops otherwise; `tracepoint` never raises (a bad field renders as `<unrepr>`) and its `name` is positional-only so a field may itself be called `name`. The Pi mirror stays stdlib-only for the minimal uv-managed Pi venv.
- Named tracepoints at decision/IO boundaries across the tooling and daemon: `scripts/config.py` (`config.env`, `config.yaml`); `scripts/pi_env_check.py` (`pi_env.ssh_run`, `pi_env.probe_result`, `pi_env.report`); `scripts/device_discovery.py` (`discovery.enumerate`, `discovery.diff`, `discovery.report`); `scripts/flash_gate.py` (`flash.validate`, `flash.gate`); `pi/battery_monitor/ina219.py` (`ina219.open`, `ina219.read` guarded by `is_debug()`, `ina219.calibrate`); `pi/battery_monitor/battery.py` (`battery.percent`, `battery.status`); `pi/battery_monitor/power_supply.py` (`power_supply.publish`); `pi/battery_monitor/daemon.py` (`daemon.config`, `daemon.poll`, `daemon.threshold`, `daemon.backoff`).
- `docs/dev/debug.md` comprehensive debugging guide for humans and AI: documents the tracepoint system (enabling `WHISKERFRAME_DEBUG` locally and for the Pi daemon via `systemctl edit`/`Environment=`), and a large set of copy-pasteable diagnostics (UPS/INA219, I2C bus, CYD serial discovery/backup/monitor, Pi host runtime, whiskerframe round-trip, config resolution) each given both raw and SSH-wrapped (`PI="ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 -C"`), an `auto_shutdown` safety note, and a quick-reference table.
- `pi/battery_monitor/daemon.py` `_threshold_level` helper classifying a state of charge as `critical`/`low`/`ok` (extracted so `_check_thresholds` stays under the McCabe complexity budget).
- `pi/battery_monitor/` railguarded battery-monitor daemon for the cyberdeck UPS Module 3S (INA219 over I2C), stdlib-only on the I2C path so it runs in the minimal uv-managed Pi venv (`pydantic`/`pyserial` only; no `smbus`).
- `pi/battery_monitor/ina219.py` pure-stdlib `INA219` driver over the Linux i2c-dev character device (`os.open` + `fcntl.ioctl` `I2C_SLAVE=0x0703`, 16-bit big-endian register I/O), exposing `bus_voltage_v`, `current_ma`, `shunt_mv`, and `power_w`; read-only except the one-time calibration (`cal=4096`) and configuration writes, and raising a typed `INA219Error` on any I2C failure so the daemon never crashes.
- `pi/battery_monitor/battery.py` pure conversion layer: `PackConfig`, `voltage_to_percent` (linear `voltage_empty..voltage_full` clamp, verified `11.67 V -> 74 %` for the 3S pack), `derive_status` (`Charging`/`Discharging`/`Full`/`Not charging`), `read_to_reading`, and the `BatteryReading` dataclass (voltage, current, percent, status).
- `pi/battery_monitor/power_supply.py` userspace `power_supply`-class publisher: `PowerSupplyPublisher` atomically writes a kernel-formatted `uevent` (`POWER_SUPPLY_NAME`, `POWER_SUPPLY_TYPE=Battery`, `POWER_SUPPLY_CAPACITY`, `POWER_SUPPLY_STATUS`, `POWER_SUPPLY_VOLTAGE_NOW` in µV, `POWER_SUPPLY_CURRENT_NOW` in µA) plus a `status.json` snapshot under `/run/battery_monitor/`, and `format_uevent`.
- `pi/battery_monitor/daemon.py` railguarded poll loop: `DaemonConfig`, `load_daemon_config` (reads the `.whiskerframe.yaml` `ups:` block via `scripts/config.py` with live-verified fallbacks), `run`, `log`, and `main`; retries transient `INA219Error`s with bounded exponential backoff instead of crashing, logs low/critical thresholds to journald, and triggers a clean poweroff only when `auto_shutdown` is true (default `false` railguard).
- `pi/battery_monitor/battery-monitor.service` hardened systemd unit running the daemon via the Pi venv interpreter (`Restart=on-failure`, `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`, `ReadWritePaths=/run/battery_monitor`, `DeviceAllow=/dev/i2c-1` with `DevicePolicy=closed`, `After=multi-user.target`).
- `pi/battery_monitor/battery-monitor.tmpfiles.conf` systemd-tmpfiles entry creating `/run/battery_monitor` on boot, and `pi/battery_monitor/install.sh` idempotent installer (installs the tmpfiles entry + unit, `daemon-reload`, `enable --now`, prints `systemctl status`).
- `pi/battery_monitor/README.md` documenting behavior, config keys, install, status reads (`status.json`, `systemctl status`, `journalctl -u battery-monitor`), and the userspace-vs-in-kernel-`ina2xx`-overlay `power_supply` note.
- `.whiskerframe.yaml` `ups:` block gained `poll_interval_seconds` (10), `auto_shutdown` (`false`), and `power_supply_name` (`cyberdeck_ups`) for the battery daemon.
- Externalized reproducible configuration: `.env` (+ committed `.env.example`) holds `PI_HOST`, `PI_USER`, `DEFAULT_KEY_PATH`, `DEFAULT_VENV_PATH`; `.whiskerframe.yaml` holds project/hardware facts (`components`, UPS/INA219 parameters, CYD serial port). New `scripts/config.py` loads both, and `scripts/pi_env_check.py` now reads its constants from them instead of hard-coding.
- Rewrote `docs/dev/manual-hardware-steps.md` into a full reproducible cyberdeck setup runbook (Pi OS + interfaces, uv host provisioning, CYD discovery/backup/flash, UPS Module 3S I2C wiring + enable + battery daemon), and corrected `docs/Schematics.md` / `docs/Pinouts.md` to the hardware I2C-1 wiring with the INA219 (`0x42`) details.
- `pi/deploy-exclude.txt` rsync exclude list so Pi deployments ship only the runtime (`whiskerframe/`, `pi/`, `scripts/`) and omit AI agent rules, dev tooling, firmware sources, docs, tests, and build artifacts.
- `pi/` Raspberry Pi host runtime: a uv-managed `pyproject.toml` (depends on `whiskerframe[serial]`), `bootstrap.sh` provisioner, and `README.md`, so the Pi installs the declared runtime into an isolated venv with a managed Python instead of using system `pip` (avoids the PEP 668 externally-managed-environment error).
- `whiskerframe` package now re-exports the public API (`XYXY`, `XYWH`, `FourXY`, `Anchor`, `TextStyle`, `DrawText`, `DrawRect`, `CommandBuilder`, `serialize`) without importing the optional Pillow/pyserial extras.
- `whiskerframe.anchors.Anchor` type mirroring imagesmacker 7.0.0's `Literal['lt', 'mt', 'rt', 'lm', 'mm', 'rm', 'lb', 'mb', 'rb']` anchor model.
- `whiskerframe.anchors.validate_anchor` enforcing the `[lmr][tmb]` two-character anchor grammar with default `"mm"`.
- `whiskerframe.anchors.resolve_anchor` decomposing a validated anchor into its horizontal and vertical keys.
- `whiskerframe.coordinates` module mirroring the imagesmacker 7.0.0 coordinate model in strict parity.
- `whiskerframe.coordinates.XYNamedTuple`, `whiskerframe.coordinates.WHNamedTuple`, `whiskerframe.coordinates.XYXYNamedTuple`, `whiskerframe.coordinates.XYWHNamedTuple`, and `whiskerframe.coordinates.FourXYNamedTuple` view structures.
- `whiskerframe.coordinates.RectangleCoordinates` abstract base class with canonical bounding-box conversion (`xyxy`, `xywh`, `fourxy`, `wh`, `as_list`, `as_tuple`) and `anchor_coordinates`.
- `whiskerframe.coordinates.XYXY`, `whiskerframe.coordinates.XYWH`, and `whiskerframe.coordinates.FourXY` rectangle representations.
- `whiskerframe.coordinates.XY` and `whiskerframe.coordinates.WH` non-negative integer coordinate types.
- `whiskerframe.coordinates.distances_squared` squared Euclidean distance helper.
- `whiskerframe.coordinates.RectangleCoordinates.anchor_coordinates` resolving a `[lmr][tmb]` anchor to an `XY` pixel via pure integer floor-division math (no Pillow).
- `whiskerframe.metrics.FontMetrics` fixed-cell glyph metrics named tuple.
- `whiskerframe.metrics.TextSize` text-block dimension named tuple.
- `whiskerframe.metrics.FONT_METRICS` static per-`font_size` metrics table (pure; no Pillow).
- `whiskerframe.metrics.DEFAULT_FONT_SIZE` default font-size selector.
- `whiskerframe.metrics.line_width` single-line width sizing helper.
- `whiskerframe.metrics.line_height` single-line glyph-cell height helper.
- `whiskerframe.metrics.line_advance` default per-line vertical advance helper.
- `whiskerframe.metrics.text_width` multiline block width sizing helper.
- `whiskerframe.metrics.text_height` multiline block stacked-height sizing helper.
- `whiskerframe.metrics.text_size` combined multiline block dimension helper.
- `whiskerframe.models.TextStyle` pydantic text presentation style (RGB565 color/bg, uint8 font_size, inverted flag).
- `whiskerframe.models.TextConfig` text-command configuration extending `TextStyle` with anchor and multiline layout.
- `whiskerframe.models.RectConfig` rectangle-command configuration (anchor, RGB565 color, filled flag).
- `whiskerframe.models.DrawText` resolved `DRAW_TEXT` (`0x01`) command model matching the wire payload layout.
- `whiskerframe.models.DrawRect` resolved `DRAW_RECT` (`0x02`) command model matching the wire payload layout.
- `whiskerframe.models.UINT8_MAX` and `whiskerframe.models.UINT16_MAX` wire-field bound constants.
- `preview` optional-dependency extra (`pillow>=10`) for the host-side preview renderer.
- `serial` optional-dependency extra (`pyserial>=3.5`) for the serial transport.
- CYD firmware sketch scaffolding under `firmware/cyd_display_link/` (PlatformIO/Arduino, ESP32 + ILI9341 + TFT_eSPI): `platformio.ini` build config and `README.md`.
- `firmware/cyd_display_link/frame.h` header-only `cyd_display_link::FrameDecoder` byte-at-a-time state machine (HuntSOF → ReadLen → ReadBody → Validate) exposing `feed`, `opcode`, `payload`, and `payload_len`; discards frames on bad CRC, unknown opcode, or oversized `LEN` and resynchronizes to the next SOF (Req 1.4), with a ~2 KB `LEN` cap.
- `firmware/cyd_display_link/render.h` header-only TFT_eSPI renderers `cyd_display_link::render_text` (Req 2.3, 2.5) and `cyd_display_link::render_rect` (Req 2.4) decoding the `DRAW_TEXT` / `DRAW_RECT` payload encodings and drawing onto a `TFT_eSPI` instance.
- `cyd_display_link::render_text` mapping the packed anchor byte to a TFT_eSPI text datum, drawing single-line and LF-split multiline text (advancing rows by `line_h`), and swapping foreground/background when the inverted flag is set; skips the command entirely on a malformed payload, an invalid packed anchor, or any anchor point outside the visible display bounds — no clipping or placement adjustment (Req 2.5).
- `cyd_display_link::render_rect` drawing a filled (`fillRect`) or outline (`drawRect`) rectangle from the resolved `DRAW_RECT` coordinates and RGB565 color (Req 2.4).
- `firmware/cyd_display_link/main.cpp` Arduino sketch entry point: `setup()` initializes the ILI9341 via TFT_eSPI (rotation 1 landscape, cleared to black) and opens `Serial` at 115200 baud matching `platformio.ini` `monitor_speed` (Req 2.2); `loop()` drains the serial RX buffer byte-by-byte through `cyd_display_link::FrameDecoder` and dispatches each complete valid frame to `render_text` (DRAW_TEXT) or `render_rect` (DRAW_RECT) (Req 1.2, 2.1).
- `cyd_display_link::anchor_to_datum` mapping the packed anchor byte (`[lmr][tmb]` nibbles) to a TFT_eSPI text datum, rejecting out-of-range nibbles.
- `cyd_display_link::point_in_bounds` rotation-aware on-screen bounds check against runtime `tft.width()` / `tft.height()`.
- `cyd_display_link::read_u16le` little-endian `uint16` payload reader, plus `kDrawTextHeaderLen`, `kDrawRectLen`, `kTextFlagInverted`, `kTextFlagMultiline`, and `kRectFlagFilled` payload-layout constants.
- `cyd_display_link::crc8` implementing CRC-8/SMBUS (polynomial `0x07`, init `0x00`, no reflection, no final XOR) over `OPCODE + PAYLOAD`, to be matched bit-for-bit by the host `whiskerframe.protocol.crc8`.
- `test/prop_serialization_roundtrip.py` property test (Property 1) asserting `whiskerframe.protocol.decode(whiskerframe.protocol.serialize(command)) == command` for any valid `whiskerframe.models.DrawText` / `whiskerframe.models.DrawRect` generated within the wire field bounds (Req 1.1).
- `test/prop_non_framebuffer.py` property test (Property 2) asserting a serialized command frame stays far below a full ILI9341 RGB565 framebuffer (320 x 240 x 2 = 153600 B), so the serial command path never carries a framebuffer (Req 1.5).
- `scripts/pi_env_check.py` Pi_Host connectivity and environment verification tooling (Req 6.1-6.3), separating a pure reporting layer from the OS/SSH invocation layer for testability.
- `scripts.pi_env_check.ComponentPresence`, `scripts.pi_env_check.EnvReport`, and `scripts.pi_env_check.ProbeResult` named tuples modeling component presence flags, the environment report, and a single probe outcome.
- `scripts.pi_env_check.missing_components` pure function returning exactly the absent components among `{python3, pip, pyserial}` in canonical order (Req 6.3).
- `scripts.pi_env_check.format_report` pure function building an `EnvReport` that continues the verification flow regardless of how many components are absent (Req 6.3).
- `scripts.pi_env_check.ssh_run` read-only SSH wrapper connecting to `Pi_Host` `10.0.0.212` as `root` with the private key referenced by path only (`/home/lyra/.ssh/id_rsa`, never read or logged); uses `BatchMode`, no shell, and an argument vector (Req 6.1).
- `scripts.pi_env_check.probe_pi_environment` running the read-only probes `python3 --version`, `pip --version`, and `python3 -c "import serial"` over SSH (Req 6.2).
- `scripts.pi_env_check.verify_pi_environment` orchestrating the SSH probes into the pure reporting layer to produce an `EnvReport`.
- `scripts.pi_env_check.PI_HOST`, `scripts.pi_env_check.PI_USER`, `scripts.pi_env_check.DEFAULT_KEY_PATH`, `scripts.pi_env_check.COMPONENTS`, and `scripts.pi_env_check.DEFAULT_PROBES` module-level configuration constants.
- `scripts.device_discovery` module implementing the `Device_Discovery` workflow: enumerate USB/serial devices and diff against a baseline to identify the CYD serial port versus the Pi serial (Req 5.1-5.4).
- `scripts.device_discovery.DeviceSnapshot` immutable snapshot of `lsusb`, `/dev/ttyUSB*`/`/dev/ttyACM*`, and `/dev/serial/by-id/` enumeration sources.
- `scripts.device_discovery.DeviceDiff` and `scripts.device_discovery.DiscoveryReport` result structures.
- `scripts.device_discovery.enumerate_devices` snapshotting all three OS enumeration sources.
- `scripts.device_discovery.capture_baseline` capturing a diff baseline (valid only when captured with no USB-serial connected, Req 5.2).
- `scripts.device_discovery.diff_devices` pure, OS-free set difference of a current snapshot against a baseline (Property 9).
- `scripts.device_discovery.report` attributing newly appeared serial nodes to the CYD and baseline-present nodes to the Pi serial, preferring reboot-stable `by-id` symlinks (Req 5.4).
- `scripts.flash_gate` module holding the pure flash-backup validation logic for the irreversible-flash safety gate (Req 7).
- `scripts.flash_gate.EXPECTED_FLASH_SIZE` constant (`0x400000`, 4 MiB) for the explicit CYD full-flash size.
- `scripts.flash_gate.BackupValidation` immutable result of a flash-backup validation, exposing `valid`, `exists`, `actual_size`, and `reason`.
- `scripts.flash_gate.validate_backup` accepting a candidate backup only when the file exists and its size exactly equals the expected flash size (non-zero); no esptool invocation or flash access (Req 7.3).
- `scripts.flash_gate.gate_decision` pure, side-effect-free permit/block decision for the irreversible flash write, permitting a write only when a validated backup exists AND an explicit positive flash size is supplied AND the operator explicitly confirmed; defaults to BLOCK otherwise (Req 7.2, 7.4, 7.5, 7.6).
- `scripts.flash_gate.GateDecision` immutable decision result whose authoritative `permitted` boolean gates the write, with diagnostic `reasons`, `detail`, `explicit_size`, `backup_valid`, and `user_confirmed` that never relax the permit.
- `scripts.flash_gate.BlockReason` enumeration of unmet gate preconditions (`MISSING_BACKUP`, `NO_EXPLICIT_SIZE`, `NOT_CONFIRMED`).
- `test/prop_flash_backup_validation.py` hypothesis property test (Property 7) asserting `scripts.flash_gate.validate_backup` reports `valid` iff a materialized temp file exists AND its size exactly equals `scripts.flash_gate.EXPECTED_FLASH_SIZE` (`0x400000`), covering the exact size, off-by-one, zero-byte, oversized, and missing-file cases (Req 7.3).
- `test/prop_flash_gate_logic.py` hypothesis property test (Property 8) asserting `scripts.flash_gate.gate_decision` permits an irreversible write iff a validated `scripts.flash_gate.BackupValidation` is present AND an explicit positive non-`bool` `int` flash size is supplied AND the operator confirmed, blocking with the matching `scripts.flash_gate.BlockReason` set otherwise (Req 7.2, 7.4, 7.5, 7.6).
- `whiskerframe.protocol` module implementing the length-prefixed serial framing and command (de)serialization for the CYD Display Link (Req 1.1, 1.5).
- `whiskerframe.protocol.SOF` start-of-frame marker and `whiskerframe.protocol.OPCODE_DRAW_TEXT`, `whiskerframe.protocol.OPCODE_DRAW_RECT`, `whiskerframe.protocol.OPCODE_CLEAR`, `whiskerframe.protocol.OPCODE_FLUSH` opcode constants (`CLEAR`/`FLUSH` reserved).
- `whiskerframe.protocol.CRC8_CHECK` CRC-8/SMBUS check value (`0xF4` over `b"123456789"`).
- `whiskerframe.protocol.crc8` computing CRC-8/SMBUS (polynomial `0x07`, init `0x00`, no reflection, no final XOR) over `OPCODE + PAYLOAD`, bit-identical to the firmware `cyd_display_link::crc8`.
- `whiskerframe.protocol.frame` wrapping an opcode and payload into a complete `[SOF][LEN][OPCODE][PAYLOAD][CRC8]` byte sequence.
- `whiskerframe.protocol.serialize` encoding a resolved `DrawText` or `DrawRect` command into framed bytes with no Pillow and no framebuffer (Req 1.1, 1.5).
- `whiskerframe.protocol.decode` validating a frame (SOF, LEN, CRC8) and reconstructing the original `DrawText` or `DrawRect`, inverting `serialize` for round-trip tests (Property 1).
- `whiskerframe.builder` module providing the pure host-side command builder (no Pillow) that resolves anchors and geometry into resolved `DrawText`/`DrawRect` commands (Req 3.1-3.5, 8.1-8.4).
- `whiskerframe.builder.CommandBuilder` stateless builder mirroring the imagesmacker 7.0.0 drawing API in strict parity.
- `whiskerframe.builder.CommandBuilder.draw_text` resolving a `[lmr][tmb]` anchor to a pixel via `RectangleCoordinates.anchor_coordinates` (Req 3.1, 3.4), stacking multiline text by `line_height` (default `metrics.line_advance`) so the block anchor coincides with the rectangle anchor (Req 3.3, 8.3), reversing line order and swapping foreground/background when `inverted` (Req 8.3), and rejecting placements inconsistent with the imagesmacker 7.0.0 model with no fallback (Req 3.5).
- `whiskerframe.builder.CommandBuilder.draw_rect` resolving an anchor against the region and emitting the canonical top-left origin, dimensions, RGB565 color, and filled flag (Req 8.2), rejecting out-of-bounds placements (Req 3.5).
- `whiskerframe.preview` optional Pillow-based host-side preview renderer (Req 4.1, 4.2, 4.4, 8.4); its Pillow import is lazy and guarded so importing the module never requires the `preview` extra and `CommandBuilder` stays operable without it (Req 4.4). Not imported by the `whiskerframe` package init.
- `whiskerframe.preview.PreviewRenderer` rendering resolved `DrawText`/`DrawRect` commands to a Pillow RGB image, reusing the builder-resolved anchor coordinates and the shared `whiskerframe.metrics` table so preview placement mirrors device placement (Property 6, Req 4.2, 8.4).
- `whiskerframe.preview.PreviewRenderer.render` producing a `PIL.Image.Image` from an iterable of resolved commands; lazily imports Pillow and raises a clear error naming the `preview` extra when Pillow is absent (Req 4.4).
- `whiskerframe.preview.rgb565_to_rgb888` expanding an RGB565 `uint16` color to an 8-bit-per-channel RGB triple for visual parity with the ILI9341.
- `whiskerframe.preview.DISPLAY_WIDTH`, `whiskerframe.preview.DISPLAY_HEIGHT`, and `whiskerframe.preview.DEFAULT_BG_RGB565` default preview-canvas constants matching the rotated ILI9341 extent and a cleared display.
- `examples/01_coordinates.py` example script constructing `XYXY`/`XYWH`/`FourXY` over one shared region and printing the `xyxy`/`xywh`/`wh`/`fourxy` conversions plus resolved `anchor_coordinates` for a subset of `[lmr][tmb]` anchors (Req 10.1).
- `examples/02_text.py` example script building a single center-anchored `DRAW_TEXT` via `CommandBuilder.draw_text`, serializing it with `serialize`, and printing the resolved command fields and framed bytes as hex (Req 10.2).
- `examples/03_multiline_text.py` example script building upright and `inverted` multiline `DRAW_TEXT` commands via `CommandBuilder.draw_text`, serializing each, and printing the payload-order lines, resolved fields, and framed bytes as hex (Req 10.3).
- `test/__init__.py` marking the `test/` runnable-script directory as a package (satisfies ruff `INP001`).
- `test/text_anchors.py` runnable test asserting single-line `DRAW_TEXT` anchor resolution for all nine `[lmr][tmb]` anchors over a known rectangle matches the imagesmacker 7.0.0 model and round-trips through `serialize`/`decode` (Req 9.1, 3.1, 3.4, 1.1).
- `test/text_anchors_multiline.py` runnable test asserting a multiline `DRAW_TEXT` block sets the multiline flag, uses the expected per-line advance, preserves (non-inverted) line ordering, and round-trips (Req 9.2, 3.3).
- `test/text_anchors_inverted_multiline.py` runnable test asserting an inverted multiline `DRAW_TEXT` block reverses payload line order and swaps foreground/background versus the non-inverted block, and round-trips (Req 9.3, 3.3, 8.3).
- `test/prop_decoder_recovery.py` `hypothesis` property test for **Property 3: Decoder recovers all valid frames and discards the rest** (Validates Req 1.4), embedding a pure-Python host-side model (`FrameDecoderModel`) of the C++ `cyd_display_link::FrameDecoder` state machine (`HuntSOF -> ReadLen0 -> ReadLen1 -> ReadBody -> ReadCRC`, discard-and-resync on bad CRC, unknown opcode, or out-of-range `LEN` against a ~2 KB cap) and asserting that, for any interleaving of `serialize()`-produced valid frames with arbitrary non-SOF garbage runs, the decoder emits exactly the valid frames' `(opcode, payload)` in original order.
- `test/prop_preview_parity.py` `hypothesis` property test for **Property 6: Preview placement mirrors builder placement** (Validates Req 4.2, 8.4), asserting that a `CommandBuilder`-resolved `DrawText`/`DrawRect` over a generated rectangle and anchor shares its placement source with `PreviewRenderer`: the resolved `(x, y)` equals `RectangleCoordinates.anchor_coordinates(anchor)` (text) / the canonical top-left (rect), and `PreviewRenderer._line_origin` computes each line origin from that same resolved `(x, y)`.
- `test/prop_anchor_resolution.py` hypothesis property test (Property 4) asserting `whiskerframe.coordinates.RectangleCoordinates.anchor_coordinates` resolves each of the nine `[lmr][tmb]` anchors over any `uint16` rectangle to the analytic left/center/right by top/middle/bottom pixel, identically for the `XYXY` and equivalent `XYWH` representations (Req 3.1, 3.4, 8.1, 8.2).
- `test/unit_anchor_validation.py` runnable unit test asserting `whiskerframe.anchors.validate_anchor` accepts all nine valid anchors unchanged, defaults to `"mm"`, and rejects malformed strings (wrong length, invalid horizontal/vertical key) with `ValueError` (Req 3.4).
- `test/prop_multiline_stacking.py` hypothesis property test (Property 5) asserting `CommandBuilder.draw_text` with `multiline=True` sets `line_h` to the supplied `line_height` or the font's default `line_advance`, preserves line order when upright, and reverses line order while swapping foreground/background when `inverted` (Req 3.3, 8.3).
- `test/prop_device_diff.py` hypothesis property test (Property 9) asserting `scripts.device_discovery.diff_devices` reports, per enumeration source, exactly `current - baseline` as added and `baseline - current` as removed (Req 5.3).
- `test/prop_env_check_reporting.py` hypothesis property test (Property 10) asserting `scripts.pi_env_check.missing_components` and `format_report` name exactly the absent components in `COMPONENTS` order, with `all_present` true iff none are missing (Req 6.3).
- `whiskerframe.transport` optional module providing a pyserial-backed serial transport for framed drawing commands; guards the pyserial import so importing the module never hard-fails when pyserial is absent, and the pure command path never imports it (Req 1.1, 4.3).
- `whiskerframe.transport.SerialTransport` opening a pyserial `Serial` port and exposing `send` (pre-framed bytes) and `send_command` (serialize-then-write), usable as a context manager or via `close`; constructing it without pyserial raises a clear `ModuleNotFoundError` naming the `serial` extra (`pip install whiskerframe[serial]`).

### Changed

- Changed the battery daemon's `auto_shutdown` to default to `true`: at/below `critical_percent` (5%) the daemon now requests a clean `systemctl poweroff` to protect the pack. The `.whiskerframe.yaml` `ups: auto_shutdown` key and the `DaemonConfig.auto_shutdown` fallback are both `true`. A spurious INA219 reading at <= 5% could therefore trigger a real poweroff; set `auto_shutdown: false` and restart the daemon to disable (see `docs/dev/debug.md`).
- `scripts/pi_env_check.py` constants (`PI_HOST`, `PI_USER`, `DEFAULT_KEY_PATH`, `DEFAULT_VENV_PATH`, `COMPONENTS`) are now sourced from `.env` / `.whiskerframe.yaml` via `scripts/config.py` rather than being hard-coded.
- `pi_env_check` now probes the Pi's uv-managed venv interpreter (`/opt/cyd-display-link/pi/.venv/bin/python`, configurable via `venv_path`) with a fallback to system `python3`, so `pyserial` installed in the venv is detected instead of being reported missing. Added `build_probes` and `DEFAULT_VENV_PATH`.
- Moved `alltheutils` from `whiskerframe`'s core runtime dependencies to the `dev` dependency group. It is only used by dev-time tooling (`dev/scripts/py/gen_config.py`, `justfile`), never by the `whiskerframe/` runtime, and it transitively pulls `jsonnet` (a C++ build) that exhausted memory when building on the Raspberry Pi Zero 2W. The runtime now depends only on `pydantic` (plus the optional `preview`/`serial` extras).
- Renamed the distribution package from `src` to `whiskerframe`, consistent with the `whiskerframe/` source directory.
- Retargeted `tool.setuptools.packages.find` discovery from `imagesmacker*` to `whiskerframe*` so the build includes the real source tree.

### Fixed

- Corrected the UPS INA219 I2C address in the hardware docs from `0x42` to `0x41` (the address detected on this build via `i2cdetect -y 1`).
- `pi_env_check.ssh_run` now shell-quotes the remote command into a single string (SSH re-parses trailing args through the remote login shell, which was word-splitting the probe script and causing a syntax error near `then`). The pip probe also accepts venv `python -m pip`, system `python3 -m pip`, or `pip3`/`pip`, since uv-managed venvs ship without pip by design.
- `pi_env_check` probes now run through a non-login `sh -c` (not `bash -lc`), so the Pi's shell rc files are never sourced. Sourcing them made each SSH probe hang until timeout (~30s total) and mis-report every component as missing; probes now return promptly and detect the venv runtime correctly.
- `whiskerframe.coordinates.FourXY` now accepts any axis-aligned rectangle, not only squares; the vertex validation checks two equal short sides, two equal long sides, two equal diagonals, and the Pythagorean relation, and width/height are taken from the bounding-box extents so orientation is preserved.

### Removed

- Removed stale `src.egg-info` and `imagesmacker.egg-info` build artifacts.

## 0.0.0

Initial Release of the package
