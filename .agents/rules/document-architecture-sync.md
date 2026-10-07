---
trigger: always_on
glob:
description: Keep the architecture docs in lockstep (Documentation Triad) and keep a write-ahead handoff journal so any agent can die and be replaced with zero context.
---

# Documentation Triad + Handoff Journal

Every architectural, technical, or design decision made in this project is
recorded from **three views at once**. Whenever such a decision lands, the SAME
change MUST update all three documents in lockstep. Do not land the code (or the
contract change) without the three doc edits in the same change.

## The Three Views

1. **`docs/dev/ai-decisions.md` — WHY (rationale).**
   The clinical technical rationale: problem statement, root cause, the decision,
   rejected alternatives, and residual risk/tradeoffs. Append-only, ordered,
   `DEC-*` entries. This is where reasoning lives.
2. **`docs/specifications/README.md` — WHAT IS (the contract).**
   The active system contract: current interfaces, wire rules, subsystem
   contracts, and the task/roadmap registry. State the system as it is *now*;
   correct any stale description rather than leaving an outdated one.
3. **`docs/dev/changelog.md` — WHEN (history).**
   The chronological record under the `(Unreleased)` section, following
   `.agents/rules/changelog.md` (Keep a Changelog headings, past-tense bullets,
   fully-qualified backticked symbols, the file touched).

## Rules

- **Lockstep, not isolation.** Do NOT dump rationale into a single isolated file
  and call it done. A decision that touches only one view is incomplete: WHY,
  WHAT IS, and WHEN must stay mutually consistent.
- **No duplication of role.** Reasoning belongs only in `ai-decisions.md`; the
  spec states the current contract (and may link to the `DEC-*` entry); the
  changelog is a terse dated line (and may link to the `DEC-*` entry). Don't
  paste the full rationale into the spec or changelog.
- **Correct, don't accrete.** When a decision supersedes an earlier one, fix the
  WHAT-IS in the spec so it describes current reality, and log the correction in
  the changelog; the superseded reasoning stays visible in the append-only
  `ai-decisions.md` history.
- **Cross-link.** Spec and changelog entries reference the owning `DEC-*` id so a
  reader can jump from *what/when* to *why*.
- **Tone.** Match each document's existing voice — `ai-decisions.md` is clinical
  and analytical; the spec is a machine-readable contract; the changelog follows
  Keep a Changelog grammar.

Leave no decision recorded in fewer than three places. Treat the triad as one
living architecture record viewed from three angles.

## Handoff Journal: `docs/dev/ai-agent-handoff.md`

A fourth artifact with a different role: **session state, not architecture.** It lets any agent die at any moment while its successor resumes with zero context. Entries live ONLY in this file and are exempt from the triad's "three places" rule.

### Write-ahead order (mandatory: log first, act second)

1. **Question:** write a `Q-` entry (OPEN) BEFORE asking the dev in chat.
2. **Answer:** write the dev's answer verbatim (ANSWERED) IMMEDIATELY on receipt, BEFORE acting on it or replying.
3. **Decision:** write a `D-` entry BEFORE executing or announcing it. Include the 1-3 line reply you are about to send the dev and the next action.
4. **Action:** write `INTENT` before any multi-step or destructive action, `RESULT` after. An INTENT with no RESULT means an agent died mid-action: investigate that first.

A decision worth logging is any choice that changes state or behavior and wasn't already dictated by the dev. Skip trivia.

### Entry format (append-only, one complete entry per write)

    ### Q-007 | 2026-10-08T03:12Z | OPEN
    Blocked: <what and why>
    Options: <a / b / c>  Recommended default: <x>
    Applies to: <task, file, DEC id>
    Answer: <verbatim, filled when ANSWERED, with timestamp>
    Reply sent: <what was said back>

Every entry must be self-contained: a fresh agent with zero context can understand and apply it. Reference `DEC-*` ids instead of repeating rationale.

### Startup protocol

On session start or takeover, read this file FIRST. Never re-ask an ANSWERED question. Surface all OPEN ones in one batch. Investigate dangling INTENTs before anything else.

### Hygiene

- **Live State block** (top of file, 15 lines max, the only rewritable part): current task, last RESULT, open blockers, next action. The journal below it is append-only.
- When the journal passes ~500 lines, move older entries to `docs/dev/handoff-archive/<date>.md`. Keep the Live State block and OPEN items.
- **NEVER record secrets**: private keys, vault passwords, setup keys, tokens. If the dev pastes one into chat, log "[secret received, redacted]" and where it was stored. Public keys are fine.
- Log decisions and reasons, not raw chain-of-thought.
- Commit this file in its own `docs(handoff)` commits, separate from feature work.
