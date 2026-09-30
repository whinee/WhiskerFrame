# Requirements Document

## Introduction

CYD Display Link connects a Raspberry Pi host to a Cheap Yellow Display (CYD, an ESP32 board with an ILI9341 TFT) over a USB-serial link. The Pi Host sends high-level drawing commands (for example, draw text or draw rectangle) over serial; custom firmware running on the CYD parses those commands and renders them locally. This is a command-based protocol, not framebuffer streaming.

The deliverable has three parts:

1. Custom CYD firmware (Arduino + TFT_eSPI, C++) that receives and renders drawing commands.
2. A Pi Host Python library that provides a pure command builder (anchor, coordinate, and geometry math with no imaging dependency on the serial command path) and an optional Pillow-based host-side preview renderer that mirrors the imagesmacker drawing model.
3. Supporting device-discovery, testing, example, and packaging workflows.

The drawing API is modeled on imagesmacker 7.0.0 (anchors, coordinates, multiline text). Because firmware flashing is irreversible, a full flash backup gate is a hard safety requirement before any write to the device.

## Glossary

- **CYD**: Cheap Yellow Display; an ESP32 microcontroller board paired with an ILI9341 TFT display, connected to the Pi Host by USB-serial.
- **CYD_Firmware**: The custom C++ firmware (Arduino framework + TFT_eSPI library) authored in this project that runs on the CYD, parses Drawing Commands, and renders them.
- **Pi_Host**: The Raspberry Pi at address 10.0.0.212 that runs the Host_Library and sends Drawing Commands to the CYD over serial.
- **Host_Library**: The uv-managed Python package in this project that builds and sends Drawing Commands and optionally renders host-side previews.
- **Command_Builder**: The component of the Host_Library that computes anchors, coordinates, and geometry and serializes Drawing Commands, with no imaging-library dependency.
- **Preview_Renderer**: The optional Pillow-based component of the Host_Library that renders a host-side preview mirroring the imagesmacker drawing model.
- **Drawing_Command**: A high-level, serializable instruction (for example, draw_text or draw_rect) sent from the Pi_Host to the CYD_Firmware over serial.
- **Device_Discovery**: The workflow that enumerates USB and serial devices and diffs them against a baseline to identify the CYD serial port.
- **Baseline**: The recorded set of USB and serial devices captured with no USB-serial device connected.
- **Flash_Backup**: A full-chip firmware image read from the CYD with esptool.py before any write operation.
- **Flash_Tool**: The esptool.py utility used to read (backup) and write (flash) the CYD flash memory.
- **Working_Package_Dir**: The `whiskerframe/` directory that holds the Host_Library source.
- **imagesmacker**: The reference drawing library (version 7.0.0) whose anchor, coordinate, and multiline-text model the drawing API mirrors.

## Requirements

### Requirement 1: Command-based serial protocol

**User Story:** As a Pi Host developer, I want to send high-level drawing commands to the CYD, so that the CYD renders content locally without receiving raw framebuffer data.

#### Acceptance Criteria

1. THE Host_Library SHALL serialize each Drawing_Command into a byte sequence transmittable over the USB-serial link.
2. WHEN the CYD_Firmware receives a complete Drawing_Command over serial, THE CYD_Firmware SHALL parse the Drawing_Command and render the corresponding output on the ILI9341 display.
3. THE Drawing_Command set SHALL include a text-drawing command and a rectangle-drawing command.
4. IF the CYD_Firmware receives a Drawing_Command that cannot be parsed, THEN THE CYD_Firmware SHALL discard the Drawing_Command and continue processing subsequent Drawing_Commands.
5. THE Host_Library SHALL transmit Drawing_Commands without embedding a framebuffer or bitmap of the full display in the serial command path.

### Requirement 2: Custom CYD firmware

**User Story:** As a firmware developer, I want custom CYD firmware built on Arduino and TFT_eSPI, so that the CYD can render drawing commands on the ILI9341 display.

#### Acceptance Criteria

1. THE CYD_Firmware SHALL be implemented in C++ using the Arduino framework and the TFT_eSPI library targeting an ESP32 with an ILI9341 display.
2. WHEN the CYD_Firmware starts, THE CYD_Firmware SHALL initialize the ILI9341 display and open the serial interface for receiving Drawing_Commands.
3. WHEN the CYD_Firmware receives a text Drawing_Command, THE CYD_Firmware SHALL render the specified text at the specified anchor and coordinates.
4. WHEN the CYD_Firmware receives a rectangle Drawing_Command, THE CYD_Firmware SHALL render the specified rectangle at the specified anchor and coordinates.
5. IF a text Drawing_Command's anchor or coordinates would render outside the visible display bounds or contain invalid parameters, THEN THE CYD_Firmware SHALL skip rendering the text Drawing_Command entirely without clipping or adjusting placement.

### Requirement 3: Pure command builder

**User Story:** As a Pi Host developer, I want a pure command builder with no imaging dependency, so that sending drawing commands does not require Pillow on the serial command path.

#### Acceptance Criteria

1. THE Command_Builder SHALL compute anchor, coordinate, and geometry values for each Drawing_Command.
2. THE Command_Builder SHALL produce serialized Drawing_Commands without importing Pillow.
3. THE Command_Builder SHALL support multiline text layout with anchor and coordinate placement.
4. WHERE a Drawing_Command specifies an anchor, THE Command_Builder SHALL compute the placement coordinates from the anchor consistent with the imagesmacker 7.0.0 model.
5. IF the computed placement is inconsistent with the imagesmacker 7.0.0 model, THEN THE Command_Builder SHALL reject the Drawing_Command and surface an error to the caller without producing fallback or approximate placement.

### Requirement 4: Optional Pillow-based preview renderer

**User Story:** As a Pi Host developer, I want an optional host-side preview renderer, so that I can visually verify drawing output before sending commands to the CYD.

#### Acceptance Criteria

1. WHERE the Preview_Renderer is enabled, THE Preview_Renderer SHALL render a host-side image of the given Drawing_Commands using Pillow.
2. THE Preview_Renderer SHALL mirror the imagesmacker 7.0.0 anchor, coordinate, and multiline-text model.
3. THE Host_Library SHALL allow the Command_Builder to operate when Pillow is not installed.
4. IF a Preview_Renderer function is invoked WHILE Pillow is not installed, THEN THE Host_Library SHALL raise a clear error identifying the missing Pillow dependency, AND THE Command_Builder SHALL remain operable in that state.

### Requirement 5: Device discovery and baseline diff

**User Story:** As an operator, I want device discovery that diffs against a baseline, so that I can identify which serial port is the CYD versus the Pi serial.

#### Acceptance Criteria

1. THE Device_Discovery SHALL enumerate USB devices using lsusb and serial devices under /dev/ttyUSB*, /dev/ttyACM*, and /dev/serial/by-id/.
2. WHERE a Baseline is used for a Device_Discovery diff, THE Baseline SHALL be valid only if it was captured with no USB-serial device connected.
3. WHEN Device_Discovery runs with the CYD connected, THE Device_Discovery SHALL diff the current device set against the Baseline.
4. THE Device_Discovery SHALL report which serial port corresponds to the ESP32 CYD and which corresponds to the Pi serial based on the Baseline diff.

### Requirement 6: Pi host connectivity and environment verification

**User Story:** As an operator, I want to connect to the Pi host and verify its Python environment, so that the host can run the library and flashing tools.

#### Acceptance Criteria

1. THE workflow SHALL connect to the Pi_Host at 10.0.0.212 as user root using the SSH key at /home/lyra/.ssh/id_rsa.
2. THE workflow SHALL verify that python3, pip, and pyserial are present on the Pi_Host.
3. IF one or more of python3, pip, or pyserial is absent on the Pi_Host, THEN THE workflow SHALL report only the specific absent component or components among {python3, pip, pyserial} and SHALL continue the normal verification flow.

### Requirement 7: Irreversible-flash safety gate

**User Story:** As an operator, I want a mandatory flash backup gate, so that the original CYD firmware is never lost to an irreversible write.

#### Acceptance Criteria

1. BEFORE any write or flash operation to the CYD, THE workflow SHALL create a Flash_Backup by reading the full flash with the Flash_Tool using an explicit flash size of 0x400000.
2. THE workflow SHALL specify an explicit flash size for every Flash_Tool read and write operation and SHALL reject an unspecified or invalid size argument.
3. AFTER creating the Flash_Backup, THE workflow SHALL validate that the Flash_Backup file exists and has a non-zero size matching the specified flash size.
4. IF the Flash_Backup file is missing or its size does not match the specified flash size, THEN THE workflow SHALL abort before any write or flash operation.
5. BEFORE any write or flash operation to the CYD, THE workflow SHALL require explicit user confirmation.
6. WHILE a validated Flash_Backup is absent, THE workflow SHALL block all write and flash operations to the CYD.

### Requirement 8: Drawing engine

**User Story:** As a Pi Host developer, I want a drawing engine for text, shapes, and multiline anchors, so that I can compose display output modeled on imagesmacker.

#### Acceptance Criteria

1. THE Host_Library SHALL provide a text-drawing operation with anchor and coordinate placement.
2. THE Host_Library SHALL provide a shape-drawing operation with anchor and coordinate placement.
3. THE Host_Library SHALL provide multiline text drawing with anchor placement.
4. THE Host_Library SHALL mirror the imagesmacker 7.0.0 anchor, coordinate, and multiline-text API signatures and behavior in strict parity, not merely with similar concepts.

### Requirement 9: Test scripts

**User Story:** As a developer, I want test scripts for anchored and multiline text, so that I can verify drawing behavior.

#### Acceptance Criteria

1. THE project SHALL provide a test script at test/text_anchors.py.
2. THE project SHALL provide a test script at test/text_anchors_multiline.py.
3. THE project SHALL provide a test script at test/text_anchors_inverted_multiline.py.

### Requirement 10: Example scripts

**User Story:** As a developer, I want example scripts, so that I can learn the coordinate, text, and multiline-text APIs.

#### Acceptance Criteria

1. THE project SHALL provide an example script at examples/01_coordinates.py.
2. THE project SHALL provide an example script at examples/02_text.py.
3. THE project SHALL provide an example script at examples/03_multiline_text.py.

### Requirement 11: Justfile recipes

**User Story:** As a developer, I want justfile recipes, so that I can run the test and example scripts with one command.

#### Acceptance Criteria

1. THE root justfile SHALL provide a `test` recipe that runs test/text_anchors.py, test/text_anchors_multiline.py, and test/text_anchors_inverted_multiline.py.
2. THE root justfile SHALL provide an `examples` recipe that runs examples/01_coordinates.py, examples/02_text.py, and examples/03_multiline_text.py.

### Requirement 12: Python project constraints

**User Story:** As a developer, I want the project managed by uv with strict linting, so that the codebase stays consistent and type-checked.

#### Acceptance Criteria

1. THE Host_Library SHALL be managed with uv and SHALL declare requires-python >=3.12.
2. THE project SHALL pass ruff, black, and mypy in strict mode.
3. THE Host_Library source SHALL reside in the Working_Package_Dir whiskerframe/.

### Requirement 13: Packaging-name resolution

**User Story:** As a developer, I want the packaging configuration corrected, so that the build targets the intended package instead of a mismatched name.

#### Acceptance Criteria

1. THE pyproject configuration SHALL declare a project name consistent with the Working_Package_Dir whiskerframe/.
2. THE pyproject configuration SHALL configure package discovery to find the whiskerframe package rather than a name of src or imagesmacker.
3. WHEN the project is built, THE build SHALL include the whiskerframe package.
