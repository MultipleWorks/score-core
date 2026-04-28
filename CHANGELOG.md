# Changelog

## 0.1.5 — 2026-04-28

### Fixed
- Repaired malformed `pyproject.toml` where the `description` and
  `readme` fields had been merged onto a single line, leaving the
  package without a valid `readme` declaration on PyPI. PyPI 0.1.5
  now ships with the updated description and the README rendered on
  the package page.

### Changed
- Package description updated to "Python reference implementation of
  the Score specification for AI skills" to match the repositioned
  specification framing.

## 0.1.4 — 2026-04-22

### Breaking
- Renamed migrate CLI target from `0.1.1` to `0.1.4`. The `0.1.1` label
  was incorrect drafting; `0.1.4` is the actual spec revision that
  introduced governance metadata fields. Passing `--to 0.1.1` now
  raises a clear error directing users to `--to 0.1.4`.

### Added
- `docs/score_governance_metadata_spec.md` — bundled alongside the
  Context API and Recording specs so the validator's R24 classification-
  combination error message points at a file that actually ships with
  the package. Previously the error referenced "the Score governance
  metadata specification" without a locatable path; the spec lived only
  in the public score repo.

### Fixed
- R24 error message now names the in-package path:
  `docs/score_governance_metadata_spec.md`.
- Body-text references to `v0.1.1` in the bundled governance spec
  corrected to `v0.1.4` (matches the Score spec revision in which
  governance metadata fields actually landed — previously a drafting
  error in the spec doc).

### Unchanged
- Migration behaviour itself: still adds `approved_by`, `approved_at`,
  `review_due`, `classification` with safe defaults.
- R24 validation logic: six valid pairs + one warning pair unchanged.
- Schema validation, Pydantic models, verify-recording CLI.

## 0.1.3 — April 2026

Adds `"mcp"` to the `Interface` Literal in both `context_api.py` and
`recording.py`. Allows MCP-server runtimes (wrapping the Context API
for Claude Code and similar tools) to self-identify without triggering
a Pydantic validation error.

## 0.1.0 — April 2026

Initial release. Schema, parser, serialiser, validator, library validator,
Context API models, Recording models, CLI (validate, library-check,
governance-init, verify-recording, migrate).

Supports Score format v0.1.1 — adds optional governance metadata fields
(`approved_by`, `approved_at`, `review_due`, `classification`) alongside
the v0.1.0 core schema. Missing governance fields are warnings; they
become errors in v0.2.
