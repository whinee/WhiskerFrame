---
trigger: always_on
glob:
description: Stop retrying and escalate when terminal commands hang or time out repeatedly.
---

# Rule: Terminal Circuit Breaker & Timeout Recovery

## Condition
If any terminal command, script execution, or tool call times out or hangs **2 times in a row**:

## Mandatory Protocol
1. **DO NOT RETRY:** Instantly stop retrying the command or tweaking command syntax.
2. **ENV DIAGNOSIS:** Assume the underlying terminal runner, shell daemon, or socket connection died at the OS level.
3. **THINK OUTSIDE THE BOX & ESCALATE:**
   - Pause tool execution completely.
   - Inform the user: *"Command timed out twice. The background terminal process appears to be dead or unresponsive."*
   - Ask the user to either restart the Kiro terminal instance, reset the shell session, or manually verify terminal health before proceeding.
