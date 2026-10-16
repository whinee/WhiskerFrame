# Domain 01: Capabilities & Offline Applications (REQ-CAP)

**Specification Prefix:** `REQ-CAP`  
**System Layer:** User-Facing Applications & Capabilities  
**Primary Implementations:** `pi/bin/wiki`, `pi/bin/wf`, Linux standard base utilities  
**Acceptance Test Plan:** `ATP-12-CAP-OFFLINE-WIKI`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Capabilities domain governs user-facing applications, offline documentation access, scripting environments, and the strict operational modalities of the WhiskerFrame Cyberdeck. The cyberdeck is designed as an air-gapped, sovereign computer; it must provide rich operational capabilities without relying on external cloud connectivity or runtime package installation while deployed in the field.

---

## 2. Formal Requirements & Normative Specifications

### REQ-CAP-01 [v0/v1]: Offline Reading & Documentation
- **Requirement:** In `v0`, the system MUST provide core offline documentation (`man`, `bash-doc`, `python3-doc`) accessible via a 53-column helper (`wiki`). In `v1`, the deck MUST host an offline Kiwix repository (e.g., Simple English Wikipedia ~1GB ZIM) on loopback, isolated from the guest demo environment.
- **Rationale:** Field operations and security audits occur in RF-denied, underground, or remote environments. Documentation must be completely self-contained.
- **Traceability:** `DEC-W29`, `TSK-15`, `ATP-12-CAP-OFFLINE-WIKI`.

### REQ-CAP-02 [v0]: Local Scripting & Development
- **Requirement:** The deck MUST support local shell scripting and Python execution on the host (`python3`, `bash`), optimized for small utilities due to the 50-key CardKB form factor.
- **Rationale:** Operators must be capable of drafting automation scripts, parsing logs, and interacting with system buses directly on the hardware without compiling native binaries.
- **Traceability:** `DEC-W16`, Section 2.09.

### REQ-CAP-03 [v0]: Text-Only Operational Modality
- **Requirement:** The deck MUST operate strictly as a text-only platform. Local machine learning or large language model (LLM) inference on the Pi Zero 2W is strictly prohibited to protect the 416 MB RAM ceiling; agent orchestration occurs exclusively on external workstation nodes.
- **Rationale:** The BCM2837B0 SoC with 512 MB LPDDR2 RAM cannot sustain local model weights without catastrophic out-of-memory thrashing and system death.
- **Traceability:** `A.03`, `DEC-W16`, `REQ-OPS-01`.

---

## 3. Actual Implementation Architecture

### 3.1 The 53-Column Offline Documentation Helper (`pi/bin/wiki`)
Implemented as a self-contained Python 3 executable (`pi/bin/wiki`) using only the standard library (`argparse`, `html.parser`, `pathlib`, `re`, `shutil`, `subprocess`, `textwrap`).

#### Key Features:
1. **Automated Column Wrapping:** Wraps all rendered markdown, plain text, and manual pages strictly to 53 columns (or custom width via `--cols`).
2. **HTML Stripping & Formatting:** `SimpleHTMLTextExtractor` parses HTML documentation (such as `python3-doc` or offline articles), converts headings and lists into formatted plaintext, and strips script tags.
3. **ANSI Escape Cleaning:** Preserves or strips terminal escape codes cleanly.
4. **Offline Topic Catalog:** Contains pre-compiled references for cyberdeck subsystems:
   - `arch`: System architecture, bus topology, and hardware maps.
   - `keyboard`: CardKB scancodes, chords, and sticky Ctrl latch timings.
   - `battery`: UPS charging curves, voltage thresholds, and INA219 details.
   - `network`: Wi-Fi persistence, 53-column helper, and NetBird mesh.
   - `security`: Guest sandbox containment, tmpfs wipes, and nftables rules.
   - `storage`: BTRFS `@data`/`@swap` topology and log2ram wear mitigation.

#### Usage Examples:
```bash
# List all available built-in offline topics
wiki --list

# Display the keyboard topic
wiki keyboard

# Read an arbitrary on-disk document wrapped to 53 columns
wiki /mnt/250GB-SSD/field-notes.md
```

### 3.2 The Unified Management Interface (`pi/bin/wf`)
`pi/bin/wf` exposes an integrated offline manual command (`wf man`):
```bash
# View offline manual index
wf man

# View specific manual topic
wf man kb
wf man wifi
wf man power
wf man profile
```

### 3.3 Text-Only Developer Tooling
The deck includes a pre-configured text-mode development environment:
- **Python 3.13 Host Runtime:** Installed under `/usr/bin/python3` and the dedicated `/opt/cyd-display-link/pi/.venv` environment.
- **Shells:** GNU Bash 5.2 configured with compact prompts (`n~ `, `g~ `).
- **Core Utilities:** `vim-tiny`, `nano`, `tmux`, `curl`, `jq`, `i2c-tools`, `w3m`.

---

## 4. Verification & Acceptance Criteria

Compliance is validated by **`ATP-12-CAP-OFFLINE-WIKI`** in `scripts/run_all_acceptance_tests.py`:
1. `wiki --list` exits with returncode 0 and enumerates all topics.
2. `wiki <topic>` formats text strictly $\le 53$ columns without line overflow.
3. Offline documentation renders instantly without network access.
4. Memory consumption during execution remains below 15 MB RAM.
