# Contradictions in Spec Interview

### 1. Artist assets redistribution VS GitHub TOS
- **A.12 / 1.08**: You stated "Code should have Mozilla Public License... I want to open source everything about this project" but want to keep the artwork in `assets/images/cess`, which has a "No redistribution... All rights are retained by the artist" license. If the repository is public on GitHub, pushing the `assets/images/cess` directory *is* redistribution. We must either `.gitignore` that directory and remove it from git history, or the artist's license must explicitly allow public repository hosting.

### 2. OTG Power & Data constraints
- **A.13**: You stated "Remove OTG, and connect RPI directly to programmer PC to debug... enabling gadget mode is important." Physics check: If Pi Power port is unconnected, and OTG port feeds the hub, the hub must backpower the Pi. But if you connect directly to a PC, the PC powers the Pi and acts as a USB host. Gadget mode works here, but means you have no hub, no SSD, and no LTE modem while debugging. Are you okay with the deck losing all its storage and networking while plugged into a PC?
