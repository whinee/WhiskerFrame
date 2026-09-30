---
trigger: always_on
glob:
description:
---

# Code Quality & Linting Rules

## After Every Edit

1. Run `just lint`.
2. Fix every error, warning, and note it reports.
3. Repeat until the run is clean.

`just lint` runs, in order, over `examples/`, `whiskerframe/`, and `test/`:

- `black` (formatting, 88-character line length)
- `no_implicit_optional` (explicit `Optional`/`| None`)
- `ruff check --fix` (lint + autofix)

Run everything through `uv` per `.agents/rules/use-uv.md` (e.g. `uv run just lint`); never invoke `python`/tools bare.

## Type Checking

- `mypy` runs in `strict` mode (configured in `pyproject.toml`).
- All functions and methods must be fully type-hinted (parameters and return types).
- Resolve every `mypy` error before considering an edit done.

## Ruff Configuration (source of truth: `pyproject.toml`)

- Line length: 88.
- Selected rule families include `ANN`, `B`, `BLE`, `C4`, `C90`, `COM`, `D`, `E`, `F`, `I`, `INP`, `N`, `PIE`, `Q`, `RET`, `RSE`, `RUF`, `S`, `UP`.
- Max McCabe complexity: 5 — keep functions small; refactor rather than suppress.
- `examples/` is exempt from `INP001`/`N999` only; everything else applies.
- Do not add blanket `# noqa`; fix the underlying issue. Use a scoped, justified `# noqa: <code>` only when a rule is genuinely inapplicable.

## Documentation

Follow `.agents/rules/api-docs.md` for docstrings and `docs/api/unreleased`:

- Every module, class, function, and method in `whiskerframe/` has a docstring following the `dev/tpl/others/autodoc.mustache` template (imperative summary, `Args:`/`Raises:`/`Returns:`/`Yields:` bullet sections, trailing blank line).
- `just docs` (pdoc3) regenerates `docs/api/unreleased/` and itself runs `just lint`.
- Keep `docs/dev/changelog.md` unreleased section current per `.agents/rules/changelog.md`.

## Markdown

- Markdown is linted against `.markdownlint.yaml` (unordered-list indent = 4 spaces; `MD013` line-length disabled; inline HTML and bare URLs allowed).

## Python Code Structure

- Library source: `whiskerframe/` (pure command path must not import Pillow; optional `preview`/`serial` extras are imported lazily).
- Tests: `test/`.
- Examples: `examples/`.
- Operator/tooling scripts: `scripts/`.
- CYD firmware (C++ / Arduino / TFT_eSPI): `firmware/`.
- `from __future__ import annotations` at the top of Python modules.
- Prefer `NamedTuple`/`dataclass(frozen=True)` and pydantic models already used in the codebase over ad-hoc dicts; keep the command path dependency-light.

## Security Requirements

- Never log or echo secret material. SSH keys are referenced by path only, never read.
- Build subprocess calls as argument vectors (no shell string interpolation of untrusted values); ruff `S` rules enforce this — address findings, do not blanket-ignore.
- Flashing the CYD is irreversible: honor the flash safety gate (validated full backup + explicit size + explicit user confirmation) before any write.

## C++ / Firmware

- Python linters (`just lint`, `ruff`, `black`, `mypy`) do not apply to `firmware/`.
- Keep firmware header-only decode logic hardware-independent where possible and documented; the host `whiskerframe.protocol` CRC/framing must stay bit-identical to `firmware/cyd_display_link/frame.h`.

## Git Commit Requirements

Use Conventional Commit style, e.g.:

```text
feat: add multiline anchor layout to command builder

- Resolve block anchor origin via coordinates.anchor_coordinates
- Stack lines by line_height; invert reverses order and swaps fg/bg
- Add round-trip and anchor property tests
```
