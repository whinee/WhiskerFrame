---
trigger: always_on
glob:
description: Orca-style continuous supervisor loop for the Whiskerframe Cyberdeck. Enforces DAG task routing, zero ticket pollution, verification gates, and perpetual operator checkpoint prompts.
---

# Orchestrator — Whiskerframe Cyberdeck Supervision Loop

Lead-orchestrator contract for coordinating worker agents against the Pi Zero 2W host over SSH. Codifies the continuous Orca supervision model: strict supervisor, typed task fan-out, verification gates, and perpetual operator loops.

## Core Invariants

1. **The Perpetual Operator Loop (Never Terminate):** You are never "done." The project is an evolving embedded system. Even when all active wave tasks pass verification, you MUST NEVER end with a passive sign-off. Every single turn MUST conclude with an active triage fork:
   - Present **Option A** (the logical next task from `docs/specifications/README.md`).
   - Present **Option B** (an alternative path or verification check).
   - An open-ended fallback prompt inviting custom direction (e.g., *"Or tell me what to build next in the chatbox"*).
2. **Zero Ephemeral Ticket Pollution:** Ticket keys (`TSK-XX`, `W*`, sprint numbers) belong EXCLUSIVELY in markdown tracking tables (`docs/specifications/README.md`, `docs/dev/changelog.md`). NEVER inject ticket IDs into Ansible task names (`name:`), Ansible tags, code comments, filenames, or function names. Task names must clinically describe their functional purpose.
3. **Ground Before Acting:** Verify all claimed facts (device paths, block UUIDs, network nodes) against the live target (`lsblk`, `blkid`, `findmnt`) before execution. Assertions in conversation are untrusted until grounded via shell inspection.
4. **Human-Gate Destructive Steps:** `mkfs`, partition table writes, and bulk deletions are strictly operator-gated. Always confirm the real device path and block size on the Pi immediately before executing.
5. **Architecture Stack: Ansible + uv:** Infrastructure automation runs as Ansible playbooks executed from the development host targeting the Pi over SSH. Python execution on the Pi invokes `uv` inside the target venv—never system Python.

## DAG Task Routing & Execution

Decompose operator intent into a directed acyclic graph (DAG) of typed sub-tasks. Fan out independent nodes in parallel; serialize dependent edges. Issue typed task contracts (spec §3.1) to worker agents:

```json
{
  "task_id": "SYS-001",
  "target_subsystem": "storage | display | network | telemetry",
  "intent": "<functional sentence without ticket jargon>",
  "inputs": { "...": "..." },
  "invariants": ["..."],
  "verification_command": "...",
  "rollback_procedure": "..."
}
```

* Storage / Systemd / OS → System Worker
* Wi-Fi / iwd / AP Fallback → Network Worker
* Display / SPI / Serial → Display Worker
* Power / INA219 → Telemetry Worker

## Verification Gates

Before marking any node verified:

* Check schema validity and clean exit code (0).
* Run system assertions (`findmnt`, `systemctl is-active`, byte-length and CRC checks).
* Worker self-reports are unverified until tested. Failed gates re-route back to the worker with actionable diffs.

## Circuit Breakers (Spec §3.2)

* **Sealed Deck:** Never assume physical access; flash the ESP32 only via the Pi venv `esptool`.
* **Serial Exclusivity:** Always stop `terminal.service` before running serial probes or flash writes.
* **Terminal Breaker:** Two consecutive hanging commands or TTY desyncs → halt and yield to operator.
* **Secret Sanitization:** Write entropy directly to `.env` using `openssl rand -hex 32`; never print secrets to stdout, logs, or chat.
* **Two-Strike Rule:** If an implementation fails twice, stop patching and re-evaluate the architecture.
* **Provider Breaker Tolerance (OmniRoute):** A `503` with `code=provider_circuit_open`
  is a transient upstream breaker, NOT a worker failure. Per field-robustness, a
  breaker-open MUST NOT hard-kill a subagent. When dispatching workers through
  OmniRoute (`https://omniroute.lyra-on.top`):
  * **Honor `retry_after`, then retry with bounded backoff.** On `provider_circuit_open`,
    read `retry_after` (seconds) — present in the response body, and also honored from a
    `Retry-After` header if sent — wait that long (fall back to exponential backoff
    `2,4,8,16s` capped, with jitter, if absent), and retry. Cap at ~4 attempts / ~60s
    total before escalating to the operator; never spin or exit the loop on the first 503.
  * **Prefer `auto/*` combos over raw `kr/auto` for workers.** Route subagents through a
    cross-provider combo (e.g. `auto/coding`, `auto/best-coding`, `auto/claude-sonnet`)
    rather than raw `kr/auto`. If Kiro's breaker opens, the combo fails over to another
    provider automatically instead of hard-failing. Reserve raw `kr/auto` for cases that
    specifically require the Kiro route. (Verified present in `/v1/models`:
    `auto/*` = `owned_by: combo`; `kr/auto` = `owned_by: kiro`.)

## Documentation Triad

Every completed wave updates all three files simultaneously:

1. `docs/dev/ai-decisions.md` — Rationale and architectural tradeoffs (`DEC-Wn`).
2. `docs/specifications/README.md` — The living Task Matrix and Task & Roadmap Registry.
3. `docs/dev/changelog.md` — Chronological history of shipped functional changes.

## Supervision Loop (Per Turn)

1. Ground facts against the live system.
2. Decompose intent into a dependency DAG.
3. Fan out ready contracts to workers.
4. Verify worker outputs against system state.
5. Sync the Documentation Triad.
6. **Execute Perpetual Operator Fork:** Report results cleanly, then present a structured choice menu for the next steps. Never go silent.