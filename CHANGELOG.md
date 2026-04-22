# Changelog

## 0.1.4 — 2026-04-22

### Breaking
- Renamed migrate CLI target from `0.1.1` to `0.1.4`. The `0.1.1` label
  was incorrect drafting; `0.1.4` is the actual spec revision that
  introduced governance metadata fields. Passing `--to 0.1.1` now
  raises a clear error directing users to `--to 0.1.4`.

### Unchanged
- Migration behaviour itself: still adds `approved_by`, `approved_at`,
  `review_due`, `classification` with safe defaults.
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
