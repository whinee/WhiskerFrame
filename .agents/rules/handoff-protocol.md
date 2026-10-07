---
trigger: always_on
glob: "*"
description: "AI Agent Handoff Protocol"
---

Agents on this project have short lifespans and lose context. `docs/dev/ai-agent-handoff.md` is how work survives between agents. Maintain it rigorously.

### When to write
- Create your entry at the START of your session, as a stub with your intended task list.
- Update it after every milestone.
- Finalize it before you stop. Assume you can be cut off at any moment.

### Append-only policy
`docs/dev/ai-agent-handoff.md` is APPEND-ONLY. Add a new dated entry at the bottom. Do not delete, rewrite, or reorder earlier entries, EXCEPT in these cases:
1. There is a gross mistake in the document (factually wrong, or it would mislead the next agent). Fix it and add a note stating what you corrected and why.
2. The user changed the requirements. Update the affected items and note the change and its date.
3. You have completed an item that an earlier entry listed as to-do. Mark it done in place (e.g. `[x]` with the date), do not delete it.

### Entry format
Each entry MUST contain these four sections. Be exhaustive. The next agent knows NOTHING that is not written here.

#### Entry Header: Date/time (UTC), agent or tool name if known, one-line session goal.

#### (a) What I have done
A summary of completed work: files created, changed, or removed, commands run, and the current state of the repo (does it build, run, and pass tests?).

#### (b) The problem the developer is facing right now
The current blocker, bug, or open question. Include exact error messages, relevant file paths, what was tried, and what failed. Write "None" if there is none.

#### (c) What still needs to be done (MOST IMPORTANT)
A complete, ordered, self-contained checklist of ALL remaining work, not only your own part. Use `- [ ]` for each task. Give each task an ID (T1, T2, ...) and keep IDs stable across entries. For each task: what to do, which files are involved, and how to know it is done (acceptance criteria). Do NOT write "see above" or "same as before". Copy over every still-open task from the previous entry. The latest entry's section (c) is the authoritative to-do list. Mention dependencies and ordering constraints between tasks.

#### (d) What I told the user to do next
Every instruction, question, or manual step you gave the user (e.g. "create the .env", "run docker compose up", "decide between X and Y"), and whether it is done, pending, or unknown. If the user owes something, the next agent must remind them.

### Reading the document
Read the TOP "read me" note and the LATEST entry in full. Read older entries only when the latest entry is unclear or you suspect a conflict.
