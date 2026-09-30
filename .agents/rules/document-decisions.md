---
trigger: always_on
glob:
description:
---

# Documentation of Engineering Decisions

For every technical, architectural, or design decision made during this project, you MUST document the rationale comprehensively in `docs/api/unreleased/ai-decisions.md`.
This includes, but is not limited to:

- Database schema changes or optimization choices
- Performance improvements (e.g., bulk database inserts, memory optimizations)
- Frontend rendering strategies (e.g., CSS `mask-image` vs standard SVGs, Jinja templating vs SPAs)
- Algorithm or logic implementations

Ensure the tone of your additions matches the highly clinical, analytical, and heavily structured tone of the existing Markdown document.

Leave no decision undocumented. You must treat `docs/api/unreleased/ai-decisions.md` as a living breathing architecture document.
