---
inclusion: always
name: self-verify-commands
description: The agent runs and verifies its own commands before handing them to the user.
---

# Self-Verify Commands

Do not hand the user a command, script, or snippet the agent has not run itself
first. The user should never be the one to discover that a command is broken.

## Protocol

- Before presenting any command as a solution, execute it in the workspace (or the
  closest safe equivalent) and confirm it produces the intended result.
- For remote/hardware commands that cannot be fully run here, exercise every part
  that CAN be run (the local logic, the exact quoting/escaping, a dry run, or the
  remote command against a reachable target) and state precisely which parts were
  verified and which could not be.
- Prefer proving behavior with a real invocation over reasoning about it. When a
  fix is claimed, re-run the failing case and show it now passes.
- If a command depends on remote state (SSH, a device, a service), trace what the
  wrapper actually sends (e.g. how SSH re-parses arguments) rather than assuming
  the local shell semantics carry over.
- Clean up any temporary artifacts a verification run creates.

## Report

When presenting a command or fix, briefly state how it was verified (what was run,
what the output was). If verification was partial, say what remains unverified and
why -- do not present unverified commands as done.
