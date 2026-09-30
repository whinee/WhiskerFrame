# Implementation Plan: CYD Display Link

## Overview

Build order front-loads the pure `Command_Builder` path (coordinates → anchors →
metrics → models → protocol → builder), which is hardware-free and testable
immediately. Optional renderer/transport, tooling, and CYD firmware follow.
Hardware-interaction tasks (device discovery, Pi SSH, flash backup, flash write) are
manual/operator steps requiring physically connected devices; they are marked
`[MANUAL]` and are optional in an automated run. The flash-write task is gated on a
validated backup plus explicit user confirmation — an irreversible hardware write.

All Python targets ruff/black/mypy strict (Req 12.2, `lint-and-fix` rule), lives under
`whiskerframe/` (Req 12.3), is uv-managed with `requires-python >=3.12` (Req 12.1,
`use-uv` rule). Every code task keeps `docs/dev/changelog.md` unreleased and
`docs/api/unreleased/ai-decisions.md` current (`changelog`, `document-decisions`,
`api-docs` rules) and removes temp artifacts (`delete-temp-files` rule).

## Tasks

- [x] 1. Packaging + project baseline
  - [x] 1.1 Fix `pyproject.toml` packaging
    - Set `[project].name = "whiskerframe"`, `requires-python = ">=3.12"`
    - Set `[tool.setuptools.packages.find].include = ["whiskerframe*"]`
    - Add `[project.optional-dependencies]`: `preview = ["pillow>=10"]`,
      `serial = ["pyserial>=3.5"]`
    - Retain ruff/black and mypy `strict = true` config
    - Remove stale `src.egg-info` / `imagesmacker.egg-info` (`delete-temp-files`)
    - Sync with `uv` lockfile (`use-uv`)
    - Record packaging rename decision in `docs/api/unreleased/ai-decisions.md`
    - _Requirements: 12.1, 12.2, 12.3, 13.1, 13.2, 13.3, 4.3_

- [x] 2. Coordinate model (`whiskerframe/coordinates.py`)
  - [x] 2.1 Implement `RectangleCoordinates` ABC + `XYXY`, `XYWH`, `FourXY`, `XY`/`WH`
    - Canonical bounding box conversion for all three representations
    - `anchor_coordinates(anchor) -> XY` pure integer math
    - Match imagesmacker 7.0.0 signatures/behavior in strict parity (Req 8.4)
    - Full docstrings + type hints per `api-docs`; changelog `Added` entry
    - _Requirements: 3.1, 3.4, 8.1, 8.2, 8.4_
  - [x]* 2.2 Write property test for anchor resolution
    - **Property 4: Anchor resolution matches the imagesmacker model**
    - **Validates: Requirements 3.1, 3.4, 8.1, 8.2**

- [x] 3. Anchor primitives (`whiskerframe/anchors.py`)
  - [x] 3.1 Implement `Anchor` type, `validate_anchor()`, `resolve_anchor()`
    - Enforce `[lmr][tmb]` grammar, default `"mm"`
    - Docstrings + type hints; changelog `Added` entry
    - _Requirements: 3.1, 3.4, 8.1, 8.2_
  - [x]* 3.2 Write unit tests for anchor validation
    - Valid/invalid anchor strings, default handling
    - _Requirements: 3.4_

- [x] 4. Font metrics table (`whiskerframe/metrics.py`)
  - [x] 4.1 Implement static width/height metrics table + line/text sizing helpers
    - Pure, no Pillow import (Req 3.2)
    - Docstrings + type hints; changelog `Added` entry
    - _Requirements: 3.2, 3.3_

- [x] 5. Command models (`whiskerframe/models.py`)
  - [x] 5.1 Implement pydantic `TextStyle`, `TextConfig`, `RectConfig`, `DrawText`, `DrawRect`
    - RGB565 colors, anchor/flags fields matching protocol payloads
    - Docstrings + type hints; changelog `Added` entry
    - _Requirements: 1.3, 8.1, 8.2_

- [x] 6. Wire protocol (`whiskerframe/protocol.py`)
  - [x] 6.1 Implement frame constants, opcodes, `crc8`, `serialize()`/`frame()`, `decode()`
    - SOF `0xA5`, `uint16` LEN LE, opcode, payload, CRC8; `DRAW_TEXT`/`DRAW_RECT` encodings
    - No Pillow import; `decode()` helper for round-trip tests
    - Docstrings + type hints; changelog `Added` entry
    - _Requirements: 1.1, 1.3, 1.5_
  - [x]* 6.2 Write property test for serialization round trip
    - **Property 1: Serialization round trip**
    - **Validates: Requirements 1.1**
  - [x]* 6.3 Write property test for non-framebuffer payload size
    - **Property 2: Command payload is not a framebuffer**
    - **Validates: Requirements 1.5**

- [x] 7. Command builder (`whiskerframe/builder.py`)
  - [x] 7.1 Implement `CommandBuilder.draw_text()` / `draw_rect()` + multiline layout
    - Resolve anchor via `coordinates.anchor_coordinates`, stack lines by `line_height`
    - `inverted` reverses line order and swaps fg/bg; no Pillow import
    - Strict parity with imagesmacker 7.0.0 API signatures + behavior (Req 8.4)
    - If computed placement is inconsistent with the imagesmacker 7.0.0 model, reject
      the command and surface an error to the caller — no fallback/approximate
      placement (Req 3.5)
    - Docstrings + type hints; changelog `Added` entry
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 8.1, 8.2, 8.3, 8.4_
  - [x]* 7.2 Write property test for multiline stacking + inversion
    - **Property 5: Multiline layout stacks lines by line height under the block anchor**
    - **Validates: Requirements 3.3, 8.3**

- [x] 8. Update package exports (`whiskerframe/__init__.py`)
  - [x] 8.1 Re-export `XYXY`, `XYWH`, `FourXY`, `Anchor`, `TextStyle`, `DrawText`,
    `DrawRect`, `CommandBuilder`, `serialize`
    - Ensure no Pillow/pyserial imported at package import time
    - Docstrings; changelog `Added` entry
    - _Requirements: 3.2, 4.3_

- [x] 9. Checkpoint - pure command path
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Test scripts (`test/`) — Req 9
  - [x] 10.1 Implement `test/text_anchors.py`
    - Nine anchors over a known rect; assert resolved `(x, y)` and byte round-trip
    - _Requirements: 9.1, 3.1, 3.4, 1.1_
  - [x] 10.2 Implement `test/text_anchors_multiline.py`
    - Multiline block; assert per-line origins stacked by `line_height`
    - _Requirements: 9.2, 3.3_
  - [x] 10.3 Implement `test/text_anchors_inverted_multiline.py`
    - `inverted=True`; assert reversed line order and swapped fg/bg in payload
    - _Requirements: 9.3, 3.3, 8.3_

- [x] 11. Example scripts (`examples/`) — Req 10
  - [x] 11.1 Implement `examples/01_coordinates.py`
    - Construct `XYXY`/`XYWH`/`FourXY`, show conversions + `anchor_coordinates`
    - _Requirements: 10.1_
  - [x] 11.2 Implement `examples/02_text.py`
    - Build + serialize a single `DRAW_TEXT`
    - _Requirements: 10.2_
  - [x] 11.3 Implement `examples/03_multiline_text.py`
    - Build + serialize a multiline `DRAW_TEXT`
    - _Requirements: 10.3_

- [x] 12. Justfile recipes — Req 11
  - [x] 12.1 Add `test` and `examples` recipes to root `justfile`
    - `test`: run the three `test/` scripts; `examples`: run the three `examples/` scripts
    - _Requirements: 11.1, 11.2_

- [x] 13. Optional Preview_Renderer (`whiskerframe/preview.py`)
  - [x] 13.1 Implement Pillow `Preview_Renderer.render(commands) -> PIL.Image`
    - Lazy/guarded Pillow import; reuse `coordinates`/`anchors`/`metrics` placement math
    - When invoked while Pillow is not installed, raise a clear error naming the missing
      Pillow dependency; `Command_Builder` must remain operable (Req 4.4)
    - Docstrings + type hints; changelog `Added` entry
    - _Requirements: 4.1, 4.2, 4.4, 8.4_
  - [x]* 13.2 Write property test for preview/builder placement parity
    - **Property 6: Preview placement mirrors builder placement**
    - **Validates: Requirements 4.2, 8.4**

- [x] 14. Optional serial transport (`whiskerframe/transport.py`)
  - [x] 14.1 Implement `SerialTransport.send(frame)` over pyserial
    - Guarded pyserial import; never imported by pure command path
    - Docstrings + type hints; changelog `Added` entry
    - _Requirements: 1.1, 4.3_

- [x] 15. CYD firmware (`firmware/cyd_display_link/`, C++ / Arduino / TFT_eSPI) — Req 2
  - [x] 15.1 Implement `frame.h` decoder state machine + CRC8
    - `FrameDecoder::feed()` HuntSOF→ReadLen→ReadBody→Validate; discard on bad CRC /
      unknown opcode / oversized LEN and resync (Req 1.4); LEN cap ~2 KB
    - _Requirements: 1.2, 1.4, 2.1_
  - [x]* 15.2 Write property test for decoder recover-and-discard (host-side model)
    - **Property 3: Decoder recovers all valid frames and discards the rest**
    - **Validates: Requirements 1.4**
  - [x] 15.3 Implement `render.h` `render_text()`
    - Map anchor byte to TFT_eSPI datum; multiline split on LF advancing by `line_h`
    - If anchor/coordinates fall outside visible display bounds or params are invalid,
      skip rendering the text command entirely — no clip/adjust (Req 2.5)
    - _Requirements: 2.3, 2.5_
  - [x] 15.4 Implement `render.h` `render_rect()`
    - Filled/outline rectangle from resolved coords
    - _Requirements: 2.4_
  - [x] 15.5 Implement `main.cpp` `setup()` / `loop()`
    - `tft.init()`, `setRotation`, clear, `Serial.begin(BAUD)`; feed decoder + dispatch
    - _Requirements: 2.1, 2.2, 1.2_

- [ ] 16. Tooling: Device_Discovery (`scripts/`) — Req 5
  - [x] 16.1 Implement device enumeration + baseline capture + diff/report logic (pure)
    - Enumerate via `lsusb`, `/dev/ttyUSB*`, `/dev/ttyACM*`, `/dev/serial/by-id/`
    - Baseline captured with no USB-serial connected; diff current vs baseline;
      report CYD tty vs Pi serial; prefer `by-id` symlinks
    - Separate pure diff function from OS enumeration for testability
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [x]* 16.2 Write property test for device diff
    - **Property 9: Device diff equals the set difference against the baseline**
    - **Validates: Requirements 5.3**
  - [ ] 16.3 [MANUAL] Operator run of Device_Discovery with CYD attached
    - Requires physical CYD connected; capture baseline then diff. Optional in
      automated runs.
    - _Requirements: 5.2, 5.3, 5.4_

- [ ] 17. Tooling: Pi connectivity + environment check (`scripts/`) — Req 6
  - [x] 17.1 Implement env-check reporting logic (pure) + SSH wrapper
    - Pure function: given presence flags over {python3, pip, pyserial}, report only
      the specific absent components and continue the normal verification flow (do not
      halt on a single missing component)
    - SSH to `10.0.0.212` as `root` with key path `/home/lyra/.ssh/id_rsa` (path only,
      never read/log key contents); run `python3 --version`, `pip --version`,
      `python3 -c "import serial"`; read-only
    - _Requirements: 6.1, 6.2, 6.3_
  - [x]* 17.2 Write property test for env check reporting
    - **Property 10: Environment check reports exactly the missing components**
    - **Validates: Requirements 6.3**
  - [ ] 17.3 [MANUAL] Operator run of Pi connectivity/env verification
    - Requires reachable Pi_Host + SSH key present. Optional in automated runs.
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 18. Tooling: Flash safety gate (`scripts/`) — Req 7
  - [x] 18.1 Implement backup-validation function (pure)
    - Succeeds iff file exists AND size == `0x400000` (non-zero)
    - _Requirements: 7.1, 7.3_
  - [x]* 18.2 Write property test for backup validation
    - **Property 7: Flash-backup validation accepts only the exact flash size**
    - **Validates: Requirements 7.3**
  - [x] 18.3 Implement flash-gate decision logic (pure)
    - Permit write iff validated backup exists AND op has explicit valid size AND
      explicit user confirmation given; else block. Reject `ALL`/unspecified/invalid size.
    - Document irreversible-action gate in `docs/api/unreleased/ai-decisions.md`
    - _Requirements: 7.2, 7.4, 7.5, 7.6_
  - [x]* 18.4 Write property test for gate logic
    - **Property 8: No flash write without a validated backup, explicit size, and confirmation**
    - **Validates: Requirements 7.2, 7.4, 7.5, 7.6**

- [ ] 19. [MANUAL] Flash backup execution — IRREVERSIBLE HARDWARE READ, gates all writes
  - [ ] 19.1 [MANUAL] Run `esptool.py read_flash 0x0 0x400000 backup.bin` on connected CYD
    - Requires physical CYD connected. Explicit size `0x400000` only. After read, run
      the backup-validation function (18.1); a validated backup is the hard precondition
      for any flash write. Optional in automated runs.
    - _Requirements: 7.1, 7.3_

- [ ] 20. [MANUAL] Flash write execution — IRREVERSIBLE, REQUIRES EXPLICIT USER CONFIRMATION
  - [ ] 20.1 [MANUAL] Flash CYD_Firmware to the device
    - **Blocked until task 19.1 completes with a validated backup AND the user gives
      explicit confirmation.** Every esptool op specifies explicit valid flash size.
      Do NOT run without validated backup + confirmation. Requires physical CYD.
      Optional in automated runs.
    - _Requirements: 7.2, 7.4, 7.5, 7.6_

- [x] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise. Confirm `just lint` and
    `just docs` are clean; changelog + ai-decisions current.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP.
- Tasks marked `[MANUAL]` are operator steps needing physically connected hardware
  (CYD over USB-serial, reachable Pi_Host) and are optional in an automated task run.
- **Irreversible-write safety:** task 20.1 (flash write) MUST NOT run unless task 19.1
  (backup + validation) is complete and the user has given explicit confirmation. Both
  are gated by the pure logic in task 18. This is an unrecoverable hardware write.
- Each task references specific requirements/properties for traceability.
- Property tests cover the 10 correctness properties where they map to pure logic
  (round-trip, non-framebuffer, decoder recovery, anchor resolution, multiline, preview
  parity, backup validation, gate logic, device diff, env check).
- Per repo rules: keep `docs/dev/changelog.md` unreleased section current, document
  decisions in `docs/api/unreleased/ai-decisions.md`, keep API docstrings current for
  `just docs`, pass `just lint` (ruff/black/mypy strict), use `uv`, delete temp files.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1", "4.1", "15.1", "16.1", "17.1", "18.1"] },
    { "id": 1, "tasks": ["2.2", "3.2", "5.1", "15.2", "15.3", "15.4", "16.2", "17.2", "18.2", "18.3"] },
    { "id": 2, "tasks": ["6.1", "15.5", "16.3", "17.3", "18.4", "19.1"] },
    { "id": 3, "tasks": ["6.2", "6.3", "7.1", "20.1"] },
    { "id": 4, "tasks": ["7.2", "8.1", "13.1", "14.1"] },
    { "id": 5, "tasks": ["10.1", "10.2", "10.3", "11.1", "11.2", "11.3", "13.2"] },
    { "id": 6, "tasks": ["12.1"] }
  ]
}
```
