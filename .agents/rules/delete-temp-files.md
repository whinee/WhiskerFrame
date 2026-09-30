---
trigger: always_on
glob:
description:
---

# Delete Temporary Files

Delete temporary files you created during a session (test scratch files, probe
output, one-off scripts, build junk, etc.) once you are done with them.

## Protected files (NEVER delete or treat as temporary)

Anything matching an entry below is a real project artifact, not temporary.
Never delete it, even if it looks generated, and never clean it up as part of a
"remove temp files" step.

<!-- Devs: add protected paths/globs here, one per line. Paths are relative to
     the repo root. Globs (`*`, `**`) are allowed. -->

- `docs/api/unreleased/ai-decisions.md`
- `docs/api/unreleased/**`
- `docs/dev/changelog.md`
- `cyd_factory_backup.bin`
- `**/uv.lock`
- `.kiro/**`
- `.agents/**`

## What counts as temporary (safe to delete)

- Scratch files created for a single test or probe (e.g. `/tmp/*.out`, ad-hoc
  `*.tmp`, throwaway repro scripts).
- Build/cache artifacts you generated (e.g. `*.egg-info/`, `build/`, `dist/`).

When unsure whether a file is temporary, do NOT delete it --- leave it and, if it matters, ask.
