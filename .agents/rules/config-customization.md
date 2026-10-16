---
trigger: always_on
glob:
description:
---

# Config Customization

Local config files hold host-specific values and must never be tracked in git.

- Never track a live config file (e.g. `.whiskerframe.yaml`); keep it gitignored.
- Commit only documented templates named `*.example.*` (e.g. `.whiskerframe.example.yaml`).
- Before running, copy the template: `cp foo.example.bar foo.bar`, then edit for your host.
- Because the live file is gitignored, `git pull` never clobbers local changes.
