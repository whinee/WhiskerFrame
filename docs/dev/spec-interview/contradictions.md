# Contradictions in Spec Interview


| ID   | Severity | Status | Title                                       | Sources                    |
| ---- | -------- | ------ | ------------------------------------------- | -------------------------- |
| C-01 | BLOCKER  | RESOLVED | Cess art terms vs. open-sourcing everything | A.12, 1.08, docs/README.md |
| C-02 | MEDIUM   | RESOLVED | OTG Power &amp; Data constraints            | A.13, topology             |


## Open

## Resolved

### C-01 · BLOCKER · RESOLVED · Cess art terms vs. open-sourcing everything

**Sources:** A.12, 1.08, docs/README.md
**You said:** "Code should have Mozilla Public License... I want to open source everything" (1.08); "No redistribution" (docs/README.md/A.12)
**Why it conflicts:** Open-sourcing everything requires distributing the repository publicly. The artist's terms explicitly state "No redistribution... All rights are retained by the artist". Distributing it via a public git repo breaks this clause and constitutes a legal blocker before the first push. Note: only unpushed local commits may be rewritten if we remove it.
**Options:**

- (a) Ask the artist for explicit permission/license update to allow public repository hosting.
- (b) Replace the art with permissible or self-made assets.
- (c) Keep the art out of the public repo (gitignore it, manage it local-only or fetch-at-install), and use `git filter-repo` on unpushed local commits to destroy its history before pushing.
**Recommendation:** (c), it permanently safely quarantines copyrighted assets while maintaining open-source code without blocking the project release.
**Q: How do you want to handle the artist's copyrighted asset redistribution?**

> A:   
> **Resolution: (a) Artist explicitly gave me permission to do whatever with it, except for commercializing it. She didn't give exact wording, but out of courtesy, I added that thingy. I am one of Artist's friends.**


### C-02 · MEDIUM · RESOLVED · OTG Power &amp; Data constraints

**Sources:** A.13, topology
**You said:** "Remove OTG, and connect RPI directly to programmer PC to debug... enabling gadget mode is important." (A.13)
**Why it conflicts:** Disconnecting the OTG hub means losing the BTRFS SSD and the LTE modem. If the Pi reboots while directly hooked to the PC via the OTG port, the system fails to mount the core data partition (`/mnt/250GB-SSD` is required by services).
**Options:**

- (a) Accept loss of storage/network while docked, making Gadget Mode a strictly degraded "recovery-only" state.
- (b) Introduce a powered USB hub so the Pi draws power independently while passing OTG data.
- (c) Forego Gadget Mode entirely and rely purely on GPIO UART for recovery/debugging (DEC-W15).
**Recommendation:** (c), since a degraded state without the unified btrfs storage crashes the deployed orchestration services.
**Q: How should we resolve the physical loss of storage when utilizing USB Gadget mode debugging?**

> A:   
> **Resolution: How would (b) work? It is already what I am doing right now. How do you think I will be able to connect the device to the programmer PC if the device is already acting as a host? (c) it is then, but that is SOOOOO janky huhuuu :C**



### C-03 · HIGH · OPEN · A5 Size Parameter vs Battery/Dongles volume
**Sources:** 2.01, A.07, topology
**You said:** "Daily Driver!" (2.01); "Less than A5 size" (A.07); "Size should be ideally less than A5" (A.07)
**Why it conflicts:** You want this to be a daily driver phone replacement that you can slip into a bag or pocket (A5 footprint limit, <65mm depth, A.11). However, the physical BOM currently includes a 10,000mAh Anker PD bank, a USB OTG hub, a ZTE LTE stick, and an RTL-SDR receiver sticking out of it. Stacking all these COTS (commercial off-the-shelf) components inside an enclosed weather-sealed case (REQ-UW-02) will easily break the <65mm thickness constraint. 
**Options:**
- (a) Abandon the RTL-SDR and LTE stick entirely, keeping it strictly to the Pi, battery, and Keyboard.
- (b) Accept a much larger or vastly thicker (>65mm) enclosure.
- (c) Disassemble the Anker battery bank, LTE stick, and USB hub to their bare PCBs and solder them directly to minimize Z-height, accepting the extremely high risk of battery puncture or hardware death.
**Recommendation:** (c) for long-term if it MUST be a phone replacement, but (a) is the only immediately executable software/hardware path for the current wave.
**Q: How do you want to resolve the physical volume limits of combining a USB Hub, LTE Modem, and 10k battery under 65mm thick?**
> A: 
**Resolution:** 
