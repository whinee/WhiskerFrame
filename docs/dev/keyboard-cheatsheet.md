# CardKB Keyboard Reference & Cheatsheet

*Document ID: DOC-KEYBOARD-CHEATSHEET*  
*Hardware: M5Stack CardKB v1.1 (I2C 0x5F, `/dev/i2c-0`)*  
*Platform: Whiskerframe Cyberdeck v0*  

---

## 1. Architecture Overview

The M5Stack CardKB is a 50-key matrix keypad managed by an onboard microcontroller. It communicates with the Raspberry Pi Zero 2W over I2C bus 0 (`/dev/i2c-0`) at 7-bit slave address `0x5F`.

Key features of the CardKB architecture:
- **Onboard Modifiers**: The physical `Sym`, `Fn`, and `Shift` (`Aa`) modifier keys are handled entirely inside the CardKB microcontroller firmware.
- **Single-Byte Protocol**: The Pi reads single bytes over I2C. Idle reads return `0x00`. When a key is pressed, the firmware emits a single byte representing ASCII or a layer-specific scancode.
- **No Native Ctrl Key**: The CardKB physical layout lacks a dedicated Control (`Ctrl`) key. Whiskerframe implements a **Sticky Modifier Latch** in software (`pi/terminal/bridge.py`) using reachable Fn-layer scancodes.

---

## 2. Special Chords & Dynamic Actions

| Action | Chord / Key | Raw Byte (Hex) | Decimal | Behavior / Output |
| :--- | :--- | :--- | :--- | :--- |
| **Ctrl Latch** | `Fn + Tab` | `0x8C` | 140 | Arms sticky Ctrl for exactly one subsequent key. Cursor turns bright yellow (`#ffe08a`). Auto-cancels on 3.0s timeout or repeat `Fn + Tab`. |
| **Cycle Geometry** | `Fn + Del` | `0x8B` | 139 | Cycles terminal font size and grid geometry: 53x30 -> 26x15 -> 17x10. |
| **Arrow Up** | `Up` | `0xB5` | 181 | Emits VT100 sequence `\x1b[A` to PTY. |
| **Arrow Down** | `Down` | `0xB6` | 182 | Emits VT100 sequence `\x1b[B` to PTY. |
| **Arrow Left** | `Left` | `0xB4` | 180 | Emits VT100 sequence `\x1b[D` to PTY (or back to user select on login). |
| **Arrow Right** | `Right` | `0xB7` | 183 | Emits VT100 sequence `\x1b[C` to PTY. |
| **Escape** | `Esc` | `0x1B` | 27 | Emits `0x1B` (or resets password buffer on login). |
| **Tab** | `Tab` | `0x09` | 9 | Shell command/path auto-completion. |
| **Backspace** | `Del` | `0x08` | 8 | Deletes previous character (`\x08`). |
| **Shift + Del** | `Shift + Del` | `0x7F` | 127 | ASCII DEL (`\x7f`). |
| **Enter** | `Enter` | `0x0D` | 13 | Carriage return / newline (`\r`). |

---

## 3. Sticky Ctrl Modifier State Machine

Because CardKB hardware cannot send simultaneous modifier state across keys, Whiskerframe provides a sequential sticky latch:

1. **Arm Latch**: Press `Fn + Tab` (`0x8C`).
   - The cursor cell background immediately recolors from standard cyan (`#2dd8ff` / `0x2EDF`) to bright yellow (`#ffe08a` / `theme.ansi[11]` / `0xFF11`).
   - A 3.0-second timer begins.
2. **Emit Ctrl Code**: Press the target character.
   - Letters (`a-z`, `A-Z`) and qualifying symbols (`@`, `[`, `\`, `]`, `^`, `_`, space) are masked with `char & 0x1F`.
   - Examples:
     * `c` / `C` -> `0x03` (`Ctrl-C` / `SIGINT`)
     * `d` / `D` -> `0x04` (`Ctrl-D` / `EOF` / logout)
     * `z` / `Z` -> `0x1A` (`Ctrl-Z` / `SIGTSTP`)
     * `[` -> `0x1B` (`Ctrl-[` / `ESC`)
     * `\` -> `0x1C` (`Ctrl-\` / `SIGQUIT`)
     * `space` -> `0x00` (`Ctrl-Space` / NUL)
   - Latch disarms immediately upon key emission; cursor reverts to cyan.
3. **Disarm / Cancel**:
   - **Toggle Cancel**: Pressing `Fn + Tab` a second time cancels the latch without sending any character.
   - **Passthrough Cancel**: Pressing a non-qualifying key (numbers `0-9`, arrows, unmapped punctuation) cancels the latch and sends that key unmodified.
   - **Timeout**: If no key is pressed within 3.0 seconds, the latch disarms silently.
   - **Login Screen**: `Fn + Tab` is explicitly dropped during the login sequence to prevent accidental modifier state injection into passwords.

---

## 4. Display Geometries (`Fn + Del`)

Pressing `Fn + Del` (`0x8B`) cycles through three font rendering engines on the Cheap Yellow Display (320x240 ILI9341):

| Font Selector | Grid Dimensions | Cell Size | Optimal Use Case |
| :--- | :--- | :--- | :--- |
| **Font 1** | **53 cols x 30 rows** | 6 x 8 px | Full system status, `wifi scan`, `ps`, manual reading, ncurses tools. |
| **Font 2 (Default)** | **26 cols x 15 rows** | 12 x 16 px | Default interactive shell, login screen, high readability under normal lighting. |
| **Font 3** | **17 cols x 10 rows** | 18 x 24 px | Extreme legibility, large status displays, presentation mode. |

---

## 5. CardKB Scancode Reference Table

### Printable & Normal Layer

| Key | Scancode (Hex) | Char |
| :--- | :--- | :--- |
| `a` - `z` | `0x61` - `0x7A` | lowercase letters |
| `A` - `Z` | `0x41` - `0x5A` | uppercase letters (via `Shift`) |
| `0` - `9` | `0x30` - `0x39` | numeric digits |
| `Space` | `0x20` | space |
| `Enter` | `0x0D` | carriage return |
| `Del` | `0x08` | backspace |
| `Tab` | `0x09` | horizontal tab |
| `Esc` | `0x1B` | escape |

### Sym Layer (Punctuation)

All punctuation in the Sym layer is emitted as standard single-byte ASCII:

```text
` ~ ! @ # $ % ^ & * ( ) _ + - = { } [ ] \ | : ; " ' < > , . ? /
```

### Fn Layer Raw Bytes (`0x80` - `0xAF` / 128 - 175)

The CardKB firmware maps `Fn + <key>` to the range `0x80` to `0xAF`. Whiskerframe reserves:
- `0x8B` (`139`): `Fn + Del` -> Font resize trigger.
- `0x8C` (`140`): `Fn + Tab` -> Sticky Ctrl modifier latch.
- `0xB4` - `0xB7`: Dedicated arrow scancodes.

Ghost bytes (`0x00`, `0xFF`, and out-of-range codes) are dropped by `cardkb.reader.KeyFilter`.
