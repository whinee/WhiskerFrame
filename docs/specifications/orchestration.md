## §3. Orchestration & Multi-Agent Architecture

The goal of this cyberdeck is to serve as an intelligent field tool. To prevent token waste, runaway subshells, or system corruption, agents operate under a **Strict Supervisor / DAG Execution Model**.

```
                   +----------------------------------+
                   |     USER PROMPT / TUI COMMAND    |
                   +-----------------+----------------+
                                     |
                                     v
                   +----------------------------------+
                   |         ORCHESTRATOR AGENT       |
                   |   - Intent Decomposition (DAG)   |
                   |   - Spec Compliance Gatekeeper   |
                   |   - Token & Cost Circuit Breaker |
                   +-----------------+----------------+
                                     |
               +---------------------+---------------------+
               | Sub-Task Spec                             | Sub-Task Spec
               v                                           v
    +----------------------+                    +----------------------+
    |    SYSTEM WORKER     |                    |    NETWORK WORKER    |
    | (Storage/Systemd/OS) |                    |   (Wi-Fi/iwd/SDR)    |
    +----------+-----------+                    +----------+-----------+
               |                                           |
               +---------------------+---------------------+
                                     v
                   +----------------------------------+
                   |     OUTPUT VERIFICATION GATE     |
                   |  - Schema match? Exit code 0?    |
                   |  - System invariants checked?    |
                   +-----------------+----------------+
                                     |
                                     v
                   +----------------------------------+
                   |      SYNTHESIZED USER UPDATE     |
                   +----------------------------------+

```

### §3.1 Task Contract Schema

The Orchestrator must never issue conversational prompts to Worker Agents. Every task fan-out must conform to a typed contract:

```json
{
  "task_id": "SYS-001",
  "target_subsystem": "storage | display | network | telemetry",
  "intent": "Mount the Samsung 250GB SSD cleanly without boot risk.",
  "inputs": {
    "device_node": "/dev/sda1",
    "mount_point": "/mnt/250GB-SSD",
    "fs_type": "ext4"
  },
  "invariants": [
    "Must bind the unit's What= to /dev/disk/by-uuid/<UUID> (via blkid), never a bare /dev/sdX.",
    "Unit must carry Options=nofail and x-systemd.device-timeout=5s so a missing SSD never blocks boot.",
    "Must run 'systemctl daemon-reload' then start the unit and confirm the mount before terminating."
  ],
  "verification_command": "systemctl daemon-reload && systemctl start mnt-250GB\\x2dSSD.mount && findmnt /mnt/250GB-SSD",
  "rollback_procedure": "systemctl disable --now mnt-250GB\\x2dSSD.mount && rm -f /etc/systemd/system/mnt-250GB\\x2dSSD.mount && systemctl daemon-reload"
}

```

### §3.2 Agent Execution Rules & Circuit Breakers

1. **The Sealed Deck Invariant:** Never emit commands assuming physical access. The ESP32 is flashed strictly via the Pi's internal venv esptool. Factory flash backup (`cyd_factory_backup.bin`) is immutable.
2. **Serial Exclusivity Lock:** Any agent interacting with the CYD via esptool or testing direct serial MUST first verify `terminal.service` is stopped (`systemctl stop terminal`).
3. **Terminal Circuit Breaker:** If an agent encounters two consecutive hanging commands or TTY desyncs, it must abort execution and yield to the user rather than spamming carriage returns or spawning zombie subshells.
4. **Secret Sanitization:** When deploying services (Komodo 2.0, API tokens), agents generate random entropy via `openssl rand -hex 32` directly into `.env` files. Agents are strictly forbidden from echoing secrets into stdout, logs, or chat context.
5. **No Ticket IDs in Ansible:** `TSK-XX` ticket identifiers must **never** appear in Ansible task names, tags, role names, or filenames — ticket provenance lives **only** in these markdown tables (Task Matrix + Task & Roadmap Registry). Ansible tags are descriptive (`memory_safety`, `native_services`, `network_automation`), not ticket-numbered.

---

