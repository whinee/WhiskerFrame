### F-06.01 · re 6.07 · reason: unstated-tradeoff
*You said:* "OH SHIT?!?!?!?! I CAN RUN ALPINE ON RASPBERRY PI?!?!!! SURE SUREEE!!! LETS DO THAT!!!!"
**Q: Are you aware that a transition to Alpine Linux requires rewriting all current Ansible roles (apt/debian-specific) and adapting them to Alpine/apk?**
(The existing infrastructure relies on `apt` for packages, systemd/sysvinit, and Debian-specific user/service management. Alpine uses `openrc` or `musl` libc, which often breaks Python wheels or Python-based services like the battery monitor.)
> A: YES!!! rewrite everything!!! alpine is so much leaner and better for the deck!!! let's do it!!!

### F-06.02 · re 6.09 · reason: physics-check/vague
*You said:* "it shouldnt take longer than 5 seconds, after which, an internal daemon kills it."
**Q: Should the guest account utilize a dedicated systemd-nspawn container (or cgroups) to enforce the 5s runtime, or rely on a `timeout` wrapper in the shell profile?**
(A `timeout` wrapper in shell profile is easily bypassed by `sh` commands. Systemd/cgroups is more robust but requires additional setup.)
> A: systemd/cgroups please! needs to be robust!!!

### F-06.03 · re 6.10 · reason: unstated-tradeoff
*You said:* "notify the user that it just recovered from a crash... to Maybe... undo what it did before it crashed"
**Q: How should the system "undo" actions taken before the crash?**
(True state-reversion (checkpointing) is non-trivial. Should this be a simple "Last known good" snapshot restore (btrfs), or just a log entry recommending manual cleanup?)
> A: last known good snapshot from btrfs, and a log entry telling me what happened! sounds perfect :3
