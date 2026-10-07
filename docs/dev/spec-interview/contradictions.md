# Contradictions in Spec Interview

| ID | Severity | Status | Title | Sources |
|---|---|---|---|---|
| C-01 | BLOCKER | OPEN | Cess art terms vs. open-sourcing everything | A.12, 1.08, docs/README.md |
| C-02 | MEDIUM | OPEN | OTG Power & Data constraints | A.13, topology |

## Open

### C-01 · BLOCKER · OPEN · Cess art terms vs. open-sourcing everything
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
**Resolution:** 

### C-02 · MEDIUM · OPEN · OTG Power & Data constraints
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
**Resolution:** 

## Resolved

