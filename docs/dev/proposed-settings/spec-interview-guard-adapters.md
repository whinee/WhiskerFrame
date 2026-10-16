# Proposed Tool Hook Settings: spec-interview-guard

This document outlines the exact hook configurations to attach `/home/lyra/.config/agent-policy/bin/spec-interview-guard` to each development environment.

Per operator policy, no tool settings or permission files are edited directly by automated agents. Please review and apply the diffs below as desired.

---

## 1. Claude Code CLI (`~/.claude/settings.json` or `.claude/settings.json`)

To enable pre-tool-use execution on all tool invocations:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "command": "/home/lyra/.config/agent-policy/bin/spec-interview-guard"
      }
    ]
  }
}
```

Or scoped explicitly to file-editing and shell execution tools:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|NotebookEdit|Bash",
        "command": "/home/lyra/.config/agent-policy/bin/spec-interview-guard"
      }
    ]
  }
}
```

---

## 2. Antigravity CLI (`~/.antigravity/hooks.json` or `.antigravity/hooks.json`)

```json
{
  "hooks": {
    "pre_tool_use": [
      {
        "command": "/home/lyra/.config/agent-policy/bin/spec-interview-guard"
      }
    ]
  }
}
```

---

## 3. Kiro (`.kiro/settings/hooks.json` or global configuration)

```json
{
  "hooks": {
    "preToolUse": [
      {
        "name": "spec-interview-guard",
        "command": "/home/lyra/.config/agent-policy/bin/spec-interview-guard",
        "matcher": ".*"
      }
    ]
  }
}
```

---

## 4. Antigravity IDE (VS Code / JetBrains / Theia settings)

In `.vscode/settings.json` or global user settings:

```json
{
  "antigravity.agent.hooks.preToolUse": [
    {
      "command": "/home/lyra/.config/agent-policy/bin/spec-interview-guard"
    }
  ]
}
```

---

## Behavior & Guarantees

- **`0.md` Human-Ownership**: All write-type tools and modifying Bash operations (`>`, `>>`, `tee`, `sed -i`, `rm`, `mv`, etc.) are denied with exit code 2. Safe read commands (`cat`, `head`, `tail`, `grep`, `less`, `more`, `diff`, `wc`, `stat`) are allowed without archiving.
- **Auto-Archiving**: Any other modification under `docs/dev/spec-interview/` triggers an automated snapshot to `docs/dev/spec-interview-archives/<timestamp>.tar.gz` with atomic creation, `flock` concurrency locking, sidecar hash comparison, and 50-archive rotation.
- **Fail-Closed**: If an archive cannot be safely written, the edit is blocked (exit 2).
- **Safe Restore**: Inspect any archive using `/home/lyra/.config/agent-policy/bin/spec-interview-restore <archive.tar.gz>` which extracts to `/tmp/spec-interview-restore-XXXXXX` and never modifies the working tree.
