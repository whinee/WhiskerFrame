---
trigger: always_on
glob:
description:
---

# Writing in docs/dev/changelog.md

This project adheres to [Keep a Changelog v1.1.0](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning v2.0.0](https://semver.org/spec/v2.0.0.html).

All updates to `docs/dev/changelog.md` must follow these rules.

## The Unreleased Section

- All ongoing work and AI agent changes must go under the unreleased header: `## <X.Y.Z> (Unreleased)`.
- The base version is the most recent released version immediately following the unreleased section (e.g., `## 6.0.0`).
- The AI agent **MUST NEVER** remove `(Unreleased)` or finalize a release section. Only the developer releases versions.

## Types of Changes & Heading Categories

Group all changes under these standard Keep a Changelog headings:

- `### Added` for new features, classes, attributes, or capabilities.
- `### Changed` for modifications in existing functionality, signatures, or behavior.
- `### Deprecated` for functionality planned for removal in upcoming versions.
- `### Removed` for functionality removed in this version.
- `### Fixed` for any bug fixes.
- `### Security` in case of vulnerabilities.

## Item Grammar and Formatting Conventions

In accordance with the existing changelog style:

1. **Past-Tense Action Verbs**: Use past tense to start descriptive bullet points (`Added`, `Changed`, `Renamed`, `Removed`, `Fixed`, `Optimized`, `Updated`).
2. **Fully Qualified Symbols**: Enclose Python identifiers, attributes, classes, and modules in backticks with their full package path (e.g., `` `imagesmacker.models.draw.TextStyle.weight` ``).
3. **Symbol-Only Additions**: Adding a new attribute or class may be written as a bare backticked symbol identifier (e.g., `` - `imagesmacker.fields.FieldCoords` ``).
4. **Context & Rationale**: When changing or renaming existing behavior, specify the rationale or target (e.g., `` - Renamed `imagesmacker.Draw.image` to `imagesmacker.Draw.background_image` `` or `` - Seperated `imagesmacker.models.draw.TextConfig` into `BaseTextConfig`, `InputTextConfig`, and `TextConfig` in order for custom parsers ``).

## Version Escalation & Developer Notification

The version number shown in `## <X.Y.Z> (Unreleased)` represents the target version for the cumulative changes made since the last release.

### Version Levels (from `docs/dev/bump.md`)

Given base version `MAJOR.MINOR.PATCH`:

- **PATCH** (`just bump patch`): Backward-compatible bug fixes or minor patches. Target: `MAJOR.MINOR.(PATCH + 1)`.
- **MINOR** (`just bump minor`): Backward-compatible new features or functionality. Target: `MAJOR.(MINOR + 1).0`.
- **MAJOR** (`just bump major`): Incompatible / breaking API changes. Target: `(MAJOR + 1).0.0`.

### Agent Workflow for Changelog Updates

1. **Label the changes**: Categorize each change under `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, or `Security`.
2. **Evaluate SemVer severity**: Determine the highest change level (patch, minor, major) among all changes present in the unreleased section relative to the base release.
3. **Escalate Unreleased Header if necessary**:
   - If the cumulative changes require a higher version level than currently indicated in `## <X.Y.Z> (Unreleased)`, update the unreleased header to match.
   - Example: If the base is `6.0.0`, current header is `## 6.0.1 (Unreleased)` (patches only), and minor changes are added, escalate the header to `## 6.1.0 (Unreleased)`.
   - If breaking changes are introduced, escalate the header to `## 7.0.0 (Unreleased)`.
4. **Notify Developer**:
   - Notify the developer that a version bump is necessary.
   - Refer to `docs/dev/bump.md` and recommend the exact command (e.g., `just bump patch`, `just bump minor`, or `just bump major`).
