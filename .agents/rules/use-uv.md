---
trigger: always_on
glob:
description:
---

# Use UV

Always use `uv` for Python command execution and environment management in this repository:

- Run Python scripts, tests, and tools using `uv run` (e.g., `uv run python ...`, `uv run pytest ...`).
- Never use `poetry` or bare `python` commands directly without `uv`.
