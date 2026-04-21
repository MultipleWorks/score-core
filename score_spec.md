# Score Format Specification
## Format version 0.1 (spec revision 0.1.4)

**Status:** Draft
**Owner:** Mark Goodchild, MultipleWorks
**Licence:** MIT
**Repository:** github.com/multipleworks/score
**Last updated:** 2026-04-16

**On versioning:** `score_version` in every skill file stays as `"0.1"` — that
is the protocol version. The spec revision number (currently `0.1.4`) tracks
changes to this specification document. Adding optional fields like governance
metadata is a spec revision, not a protocol bump.

---

## What Score Is

Score is a portable, human-readable format for encoding organisational knowledge and skills. A Score skill file describes what an AI assistant should know and how it should behave in a specific context — written in plain markdown so any human can read and edit it, and any LLM can consume it.

- **Score is LLM-agnostic.** A skill written for one model works with any other.
- **Score is tool-agnostic.** A skill written for one assistant platform can be loaded into any Score-compatible system.
- **Score is human-readable.** A skill file can be opened in any text editor, tracked in git, and maintained by non-developers.

---

## File Format

A Score skill file is a markdown file with YAML frontmatter.

- File extension: `.md`
- Encoding: UTF-8
- The YAML frontmatter block is delimited by `---` at the start and end
- The body begins immediately after the closing `---`
- File name must match the `name` field exactly, with `.md` extension

Example filename: `proposal-review.md` for a skill with `name: proposal-review`.

---

## Schema — Required Fields

All fields are required. A skill file missing any required field is invalid and must be skipped by the loader with a warning. It must never cause a crash.

### `score_version`
- Type: string
- The version of the Score format this file targets
- Currently always `"0.1"` — the only published version
- Loaders may use this field to apply version-specific parsing rules in the future. For v0.1, a loader should accept the value `"0.1"` and warn (not error) on any other value
- Example: `score_version: "0.1"`

### `name`
- Type: string
- Format: kebab-case (lowercase letters, hyphens only, no spaces, no special characters)
- Must be unique across the entire skill library, not just within a folder
- Must match the filename exactly (without the `.md` extension)
- Example: `proposal-review`, `mw-brand`, `meeting-prep`

### `description`
- Type: string
- Format: single sentence, ending with a full stop
- Describes what the skill does — not when to use it (that is what triggers are for)
- Must not contain line breaks
- Example: `"Applies MW proposal standards and quality criteria to client proposals."`

### `version`
- Type: string
- Format: semantic versioning — `major.minor.patch`
- Start all new skills at `0.1.0`
- Increment patch (`0.1.x`) for content edits and trigger additions
- Increment minor (`0.x.0`) for structural changes or output format changes
- Increment major (`x.0.0`) when the skill is considered stable and production-tested
- Example: `0.1.0`, `0.2.1`, `1.0.0`

### `owner`
- Type: string
- The email address or name of the person responsible for maintaining this skill
- This person is notified (in Phase 2+) when the skill is flagged as stale
- Example: `mark@multipleworks.com.hk`

### `triggers`
- Type: list of strings
- Minimum: 2 entries. Maximum: 10 entries.
- Each trigger is a phrase or keyword that activates this skill
- Matching is case-insensitive substring match against the user message
- The message is padded with spaces before matching: `f" {message.lower()} "` to ensure edge-of-string words match correctly
- Known limitation: trailing punctuation (e.g. `"about mw?"`) may not match space-padded signals — see Known Limitations section
- Triggers must be phrases a user would naturally say
- No trigger phrase should be a single word — too broad, causes false positives
- Triggers must be unique across the library unless co-firing is intentional
- Reference skills (brand, credentials, pricing) should have at least 8 triggers
- Action skills (proposal review, email drafting) can work with 4–6

### `tags`
- Type: list of strings
- Must be chosen from the approved vocabulary (see Tags section below)
- Most skills should have 1–2 tags
- If a skill needs 4 or more tags, consider splitting it

### `active`
- Type: boolean (`true` or `false` — not the strings `"true"` or `"false"`)
- `true`: skill loads at runtime and fires when triggered
- `false`: skill is disabled but not deleted. Use when a skill is under revision.

### `created`
- Type: string
- Format: ISO 8601 date — `YYYY-MM-DD`
- Set once when the skill file is first created. Never change it.

### `updated`
- Type: string
- Format: ISO 8601 date — `YYYY-MM-DD`
- Must be updated every time any part of the file changes — frontmatter or body
- Must be greater than or equal to `created`

---

## Governance Metadata (new in v0.1.1)

Four governance fields were added in Score v0.1.1. They are **optional in v0.1.1** (missing fields produce warnings, not errors) but will be **required in v0.2**. The migration path is: add them now via `score migrate --to 0.1.1`, populate `approved_by` and `approved_at` as a human review step, then v0.2 flips the warnings to errors.

### `approved_by`
- Type: string (optional in v0.1.1, required in v0.2)
- The person or identifier who approved this version of the skill for production use
- Format is free text — email addresses, full names, or opaque identifiers all work
- Example: `mark@multipleworks.com.hk`

### `approved_at`
- Type: string (optional in v0.1.1, required in v0.2)
- Format: ISO 8601 date — `YYYY-MM-DD`
- The date this version was approved
- Must be greater than or equal to `updated` — approval applies to content as at the updated date
- Example: `2026-04-16`

### `review_due`
- Type: string (optional in v0.1.1, recommended)
- Format: ISO 8601 date — `YYYY-MM-DD`
- A date by which this skill should be reviewed for ongoing accuracy
- The `score migrate --to 0.1.1` command defaults this to 12 months from today
- A `review_due` in the past is a warning

### `classification`
- Type: string (optional in v0.1.1, required in v0.2)
- One of: `public`, `internal`, `confidential`
- Governs LLM routing in Score-compatible runtimes:
  - `public` and `internal`: routed per the organisation's default LLM setting
  - `confidential`: **always** routed to a local model, never to a cloud LLM (hard constraint, not configurable)
- `score migrate --to 0.1.1` defaults new entries to `internal` as the safe conservative choice

---

## Schema — Example

```yaml
---
score_version: "0.1"
name: meeting-prep
description: Prepares the user for client and prospect meetings with agenda, context summary, and key questions.
version: 0.1.0
owner: mark@multipleworks.com.hk
triggers:
  - prep for my meeting
  - meeting prep
  - prepare for my call
  - before my call with
  - briefing for
  - meeting briefing
  - call prep
  - getting ready for my meeting
tags:
  - operations
  - client-delivery
active: true
created: 2026-04-06
updated: 2026-04-06
---

You are helping the user prepare for an upcoming meeting.
Produce a concise, useful briefing — not a wall of text.

Structure your response as:

1. **Meeting purpose** (1–2 sentences): What is this meeting trying to achieve?
2. **Key context**: What does the user need to know walking in?
3. **Agenda suggestion**: 3–5 items with approximate time allocation.
4. **Questions to ask**: 3–5 sharp questions that move the conversation forward.
5. **Watch-outs**: Any sensitivities, objections, or dynamics to be aware of.

Keep the whole briefing to one screen.
```

---

## The Skill Body

The body is the content injected into the LLM system prompt when the skill fires.

**Rules:**
- Write in the second person imperative: "Review the proposal for..." not "This skill reviews proposals..."
- Keep body length under approximately 500 words. If longer, split into two skills.
- The body must be self-contained. It cannot reference another skill or assume the LLM has read another file.
- Do not duplicate content that lives in another skill.
- Leave no gaps for the LLM to fill with invention. Reference skills covering factual information (brand, rates, policy) must be exhaustive on locked values.
- Markdown formatting is supported: headers, bullet points, tables, bold, italic.

**The 500-word limit exists for a reason.** When multiple skills fire simultaneously, all their bodies are concatenated into the system prompt. Short, focused bodies compose better than long ones.

---

## Tags — Approved Vocabulary

Use only these tags. Do not invent new tags without adding them to this list and to the Score Design Reference document.

| Tag | When to use |
|-----|-------------|
| `brand` | Positioning, tone, messaging, visual identity |
| `proposals` | Proposal writing, review, quality control |
| `client-delivery` | Engagement execution, client communication |
| `pricing` | Rate card, value-based pricing, fee structures |
| `operations` | Internal workflows, meeting prep, admin |
| `communications` | Emails, messages, external written communication |
| `strategy` | Business strategy, product thinking, market analysis |
| `research` | Market research, competitor analysis, synthesis |
| `coaching` | Leadership coaching, founder and CTO development |
| `maestro` | Skills about the Maestro product and Score format |

---

## Validation Rules

A Score-compatible loader must enforce these rules. Invalid files are skipped with a warning — they never cause a crash or prevent other skills from loading.

1. All required fields must be present
2. `name` must be kebab-case and unique across the library
3. `name` must match the filename (without `.md` extension) exactly
4. `description` must be a single sentence with no line breaks, ending with a full stop
5. `version` must be valid semver (`x.y.z` where x, y, z are integers)
6. `triggers` must have at least 2 entries and at most 10 entries
7. `active` must be boolean `true` or `false` — not a string
8. `created` and `updated` must be valid ISO 8601 dates (`YYYY-MM-DD`)
9. `updated` must be greater than or equal to `created`
10. `tags` must only contain values from the approved vocabulary
11. `body` must be non-empty

---

## Versioning

Skills use semantic versioning independently of the Score format version. The format version (currently 0.1) is separate from any individual skill version.

| Increment | When to use |
|-----------|-------------|
| Patch `0.1.x` | Wording edits, additional context, new trigger phrases |
| Minor `0.x.0` | New sections, output format changes, trigger restructure |
| Major `x.0.0` | Skill is stable and production-tested, or purpose has fundamentally changed |

Always increment version and update the `updated` date together. Never edit a skill without doing both.

**Renaming a skill.** Skill names should be stable once a skill is in production. If a rename is necessary, rename the file with `git mv` (not delete + create) so the version history is preserved as a rename. Update the `name` field and filename together — they must match. Treat the rename as a structural change and bump the minor version (`0.x.0`). If other skills or code referenced the old name, update those references in the same commit.

---

## Skill Library Structure

Skills are stored as `.md` files. They can be organised into subdirectories. The loader searches recursively. Subdirectory names have no semantic meaning — they are for human organisation only.

Recommended structure:

```
skills/
  mw/          # MultipleWorks-specific skills
  maestro/     # Skills about Maestro and Score itself
  generic/     # General-purpose skills
```

Skill names must be unique across the entire library regardless of subdirectory. Two skills in different folders cannot share a name.

---

## Execution Model

When a user message is received:

1. The message is lowercased and padded with spaces: `f" {message.lower()} "`
2. Every active skill's trigger phrases are checked against the padded message
3. All skills with at least one matching trigger are considered fired
4. Fired skills' bodies are concatenated and injected into the system prompt
5. The query is routed to the appropriate LLM with the assembled context

**When zero skills fire:**

- If the query contains an organisational domain signal, the honesty protocol activates: a configured response is returned and the query is logged to the gap log. The LLM is not called.
- If no organisational signal is detected, the query routes to the local model as a general knowledge query.

The domain classifier, honesty protocol, and gap log are host-implementation details — not part of the Score format. A compatible loader does not have to implement them.

---

## Execution Hints (Optional Fields)

The following frontmatter fields are **optional** and used only by hosts that support multi-turn conversational flows. They are **not** part of the required v0.1 schema. A Score-compatible loader that does not implement session locking must ignore these fields silently — never warn, never reject the skill.

### `locks_session`
- Type: boolean
- When `true`, the skill takes exclusive session control: while locked, no other skills co-fire for the same session. Used by skills that run structured multi-turn flows (e.g. a quote-building conversation) where co-firing skills would inject conflicting instructions.
- Default: `false`

### `lock_release_signals`
- Type: list of strings
- Substrings that, when found in the LLM's response, release the session lock. Typically used to detect completion markers a skill emits when a flow finishes.
- Example: `["[QUOTE_READY]"]`
- Default: `[]`

### `cancel_phrases`
- Type: list of strings
- Phrases the user can say mid-flow to cancel and release the lock. Matching is case-insensitive substring against the user message.
- Example: `["cancel", "stop", "never mind", "forget it", "start over"]`
- Default: `[]`

### Example

```yaml
locks_session: true
lock_release_signals:
  - "[QUOTE_READY]"
cancel_phrases:
  - cancel
  - stop
  - never mind
```

Implementations that do not support locking should load skills with these fields successfully and treat them as normal non-locking skills.

### `ui_theme`
- Type: object (YAML mapping)
- Optional block that provides structured UI theming values for Score-compatible management tools. A loader that does not implement UI theming must ignore this block silently.
- Fields (all optional within the block):
  - `brand_name` — display name for the management UI
  - `primary_color` — hex colour string (e.g. `"#0F4C75"`)
  - `accent_color` — hex colour string
  - `logo_url` — URL to a logo image, or null
  - `heading_font` — font family name for headings
  - `body_font` — font family name for body text
  - `tagline` — short brand tagline
- When multiple active skills have `ui_theme` defined, the skill with the `brand` tag takes precedence. Only one brand skill should define `ui_theme` in a well-maintained library.
- Example:

```yaml
ui_theme:
  brand_name: "MultipleWorks"
  primary_color: "#0F4C75"
  accent_color: "#00C9B7"
  heading_font: "Gill Sans MT"
  body_font: "Calibri"
  tagline: "Big 4 expertise, boutique execution"
```

Implementations that do not support UI theming should load skills with `ui_theme` successfully and ignore the block entirely.

---

## Known Limitations — v0.1

These are documented limitations of the current implementation. They are not silent failures — they are tracked and will be addressed in future versions.

**Trailing punctuation in domain signals.** A query ending with a signal word followed by punctuation (e.g. `"what about mw?"`) may not trigger the domain classifier because the space-padded signal `" mw "` does not match before `"?"`. The gap log will surface if this is frequent. Fix in v0.2: regex word boundaries.

**Substring matching only.** Trigger matching is substring-based, not semantic. `"Give me a company overview"` will not match a trigger of `"MW brand summary"` even though the intent is the same. Fix in v0.2: semantic/embedding-based matching.

**No skill composition declarations.** Skills compose implicitly — all fired skills' bodies are concatenated. There is no mechanism to declare that a skill should always or never fire alongside another. Planned for a future version.

**Trigger limit of 10 is deliberate.** The maximum of 10 triggers was pressure-tested against a production skill that grew to 17 triggers during dev iteration. The skill was reduced to 9 triggers (covering 12 of the 17 original phrasings via substring-maximising consolidation) rather than raising the limit. A skill that genuinely needs more than 10 triggers is a signal the skill is too broad and should be split. **The spec limit holds at 10 — redesign the skill, not the spec.** Phrasings that stop matching after consolidation hit the gap log if users say them, which is the right feedback loop for deciding whether to swap triggers in or out.

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-04-05 | Initial specification. Established schema, validation rules, execution model, and known limitations. |
| 0.1.1 | 2026-04-05 | Added Execution Hints section (optional locking fields), skill-rename guidance, and trigger-limit design rationale. No breaking changes. |
| 0.1.2 | 2026-04-10 | Documented `score_version` as a required field (was implicit in implementation but undocumented). Tightened validation rule #4 wording, added trigger maximum to rule #6, added rule #11 for non-empty body. No format changes — only spec accuracy fixes against the current implementation. |
| 0.1.3 | 2026-04-12 | Added `ui_theme` as an optional execution hint. Allows brand skills to provide structured UI theming values (brand name, colours, fonts, tagline) for Score-compatible management tools. |
| 0.1.4 | 2026-04-16 | Added governance metadata section: `approved_by`, `approved_at`, `review_due`, `classification`. Optional in this revision (warnings if missing). Will be required in the next protocol bump (0.2). `classification: confidential` forces local-only LLM routing. `score migrate --to 0.1.1` CLI command added to score-core to apply safe defaults. |

---

## Licence

The Score format specification is released under the MIT Licence. You are free to implement Score-compatible tools, parsers, and loaders. Reference implementations are available at [repository URL].
