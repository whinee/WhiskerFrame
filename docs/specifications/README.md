# WhiskerFrame / Cyberdeck Specifications

This directory holds the definitive architectural contracts and rules for the Cyberdeck project. 
It is split into domain-specific files for easier consumption.

## Doc Map & Reading Order

1. **[architecture.md](architecture.md)** — System role, physical topology, constraints, and base design decisions.
2. **[contracts/wire-protocol.md](contracts/wire-protocol.md)** — Control codes and data framing between microcontroller and Pi.
3. **[terminal.md](terminal.md)** — TUI design, display rendering rules, and input handling.
4. **[display-color.md](display-color.md)** — RGB565 handling and palette requirements.
5. **[storage-mount.md](storage-mount.md)** — BTRFS subvolumes, systemd mount units, and swap topology.
6. **[orchestration.md](orchestration.md)** — Autonomous agent execution environment, DAGs, and task boundaries.
7. **[tasks.md](tasks.md)** — Task matrix and roadmap registry.
8. **[sops.md](sops.md)** — Standard Operating Procedures for dev/maintenance.
9. **[product-requirements.md](product-requirements.md)** — User-facing capabilities, limits, and verified requirements (`REQ-*`).
