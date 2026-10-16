# Screen Observability & Visual Verification Specification

**Specification ID:** `SPEC-SCREEN-OBSERVABILITY`  
**Subsystem:** Terminal & Display Subsystem (`REQ-TERM`)  
**Associated Scripts:** `scripts/visual_verify.py`, `scripts/convert_splash.py`  
**Test Suites:** `test/prop_preview_parity.py`, `test/prop_non_framebuffer.py`, `test/test_demo_art.py`  

---

## 1. Physical Display Inspection & Observability Channels

The cyberdeck display subsystem (`firmware/cyd_display_link/`, `whiskerframe/`) operates entirely via **command-driven serialization**, bypassing Linux kernel framebuffers (`/dev/fb*`) entirely to eliminate SPI bus saturation and memory overhead on the Raspberry Pi Zero 2W.

```text
+-------------------+      UART (115200)       +-----------------------+
| Pi Zero 2W Bridge | -----------------------> | ESP32-2432S028 (CYD)  |
| (whiskerframe)    |  [SOF][LEN][OP][PAYLOAD] | ILI9341 320x240 Panel |
+-------------------+                          +-----------------------+
```

### Observation Channels:
1. **Host-Side Preview Renderer (`whiskerframe.preview.PreviewRenderer`)**:
   - Reuses resolved command coordinates and shared metrics (`whiskerframe.metrics`) to render exact pixel representations of `DrawText`, `DrawRect`, and `DrawCells` commands onto a Pillow-backed RGB canvas (`320x240`).
   - Guarantees 100% visual parity with device output (Property 6, Req 4.2, 8.4).
2. **Terminal Character Grid (`pi/terminal/grid.py`)**:
   - Maintains a double-buffered `cols x rows` character matrix (e.g., 53x30 for 6x8 font, 40x20 for 8x12 font).
   - Computes incremental cell diffs (`Grid.diff`) and keyframe repaints (`Grid.full_repaint`) to emit minimal `DRAW_CELLS` (`0x03`) wire commands.
3. **Serial Protocol Mirroring & Logging**:
   - Every transmitted frame can be intercepted and decoded via `whiskerframe.protocol.decode` for headless inspection and property testing (`test/prop_non_framebuffer.py`).
4. **Physical Panel Verification**:
   - ESP32 firmware running `TFT_eSPI` drives the ILI9341 320x240 LCD in landscape rotation (`rotation = 1`), with panel inversion enabled (`tft.invertDisplay(true)`) to correct native RGB primary inversion.

---

## 2. Reproducible Visual Verification Tool (`scripts/visual_verify.py`)

The reproducible verification script compiles sample drawing commands, generates a high-fidelity PNG preview image, and exports a text-grid layout representation.

### Execution:
```bash
uv run python scripts/visual_verify.py --output-dir docs/dev/specimens/
```

### Output Artifacts:
- `docs/dev/specimens/visual_verify_render.png`: Full-color graphical rendering of text blocks, bounding rectangles, status bars, and UI elements.
- `docs/dev/specimens/visual_verify_grid.txt`: ASCII/text grid dump representing terminal cell contents at the active geometry.

---

## 3. Acceptance Criteria & Verification Matrix

| Acceptance Test / Property | Subsystem | Validation Mechanism | Status |
|---|---|---|---|
| **Property 2 / Req 1.5** | Wire Protocol | Serial frames never carry raw framebuffers (<153KB), verified by `test/prop_non_framebuffer.py`. | PASSED |
| **Property 6 / Req 4.2** | Preview Parity | `PreviewRenderer` coordinates match builder origin math exactly (`test/prop_preview_parity.py`). | PASSED |
| **REQ-TERM-02** | Terminal Grid | 53x30 cell-differential rendering via `Grid.diff` and `DrawCells` (`0x03`). | PASSED |
| **REQ-TERM-07** | Coprocessor Blitting | Chunked `DRAW_IMAGE` (`0x05`) streaming (2 rows, 1,280 bytes) verified by `test_demo_art.py`. | PASSED |
