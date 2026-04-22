# Score Format – Governance Metadata Fields
## Specification Update v0.1.4

**Status:** Draft  
**Author:** Mark Goodchild, MultipleWorks  
**Repository:** github.com/multipleworks/score  
**Last updated:** 2026-04-22  
**Supersedes:** score_spec.md v0.1.0 (additive – no breaking changes)

---

## Contents

- [Overview](#overview)
- [Why now](#why-now)
- [New fields](#new-fields)
- [Updated schema](#updated-schema)
- [Validation rules](#validation-rules)
- [Classification and LLM routing](#classification-and-llm-routing)
- [Migration from v0.1.0](#migration-from-v010)
- [Forward compatibility with v0.2](#forward-compatibility-with-v02)
- [Example skill files](#example-skill-files)
- [Changelog](#changelog)

---

## Overview

Score v0.1.4 adds four optional governance metadata fields to the skill file frontmatter:

| Field | Type | Purpose |
|-------|------|---------|
| `approved_by` | string | Who approved this version of the skill. |
| `approved_at` | date | When this version was approved. |
| `review_due` | date | When this skill is next due for review. |
| `classification` | string | Data sensitivity classification of the skill's content. |

All four fields are optional in v0.1.4. A v0.1.0 skill file without these fields remains valid and will load without warnings. A v0.1.4 skill file with these fields is backward-compatible – any v0.1.0-compatible loader that does not recognise these fields will ignore them without error.

In Score v0.2, `approved_by`, `approved_at`, and `classification` will be required fields. `review_due` will remain optional.

---

## Why now

Score v0.1.0 was designed for a single-user or small-team context where governance is informal – the person who writes the skill and the person who approves its use are often the same person, and the approval process is a git commit.

The Maestro management layer now has a working approval workflow engine. Skills go through a named approval cycle before going live. The approval is recorded in Maestro's database. But the skill file itself carries no record of that approval – the governance metadata lives in the product, not in the format.

This creates a problem for portability. A skill file exported from Maestro and loaded into a third-party Score-compatible runtime carries no governance information. An auditor examining the skill library cannot determine from the files alone who approved each skill or when. The Independent Review has to cross-reference Maestro's internal records rather than reading the skill files directly.

Adding these fields to the frontmatter closes that gap. The skill file becomes self-describing from a governance perspective. The Independent Review can work from the files alone.

The fields are optional in v0.1.4 rather than required because existing skill libraries should not break on update, and because not every Score deployment has formal approval workflows. A solo developer building personal skills does not need an approver field. An enterprise deploying Maestro does.

---

## New fields

### `approved_by`

**Type:** string  
**Required in:** v0.2  
**Format:** An identifier for the approver. This should be a name, an email address, or an opaque identifier consistent with the organisation's identity system. It must be human-readable – the purpose is to establish a named, accountable approver for every skill version.

```yaml
approved_by: mark.goodchild@multipleworks.com.hk
```

or

```yaml
approved_by: Mark Goodchild
```

**Governance note:** The `approved_by` value should identify the person who took responsibility for approving this specific version of the skill – not the author, not the system, and not a team name. Accountability requires a named individual. Team names and role titles are not acceptable values in a deployment where Independent Review is anticipated.

**In Maestro:** Populated automatically from the approver's account when they approve a skill version through the governance workflow. Cannot be set manually by the skill author – only by the approver action.

---

### `approved_at`

**Type:** date (ISO 8601, YYYY-MM-DD)  
**Required in:** v0.2  
**Format:** The date on which this version was approved. Date only – no time component. The precise timestamp of approval is recorded in Maestro's audit log and in The Recording. The date in the skill file is for human readability and cross-referencing.

```yaml
approved_at: 2026-04-16
```

**Governance note:** `approved_at` must be on or after the `updated` date. A skill cannot be approved before it was last modified. If `approved_at` predates `updated`, the skill file is malformed – this indicates either a data error or that the skill was modified after approval without a new approval cycle.

**In Maestro:** Populated automatically at the moment of approval. Cannot be back-dated.

---

### `review_due`

**Type:** date (ISO 8601, YYYY-MM-DD)  
**Required in:** Never (remains optional in v0.2)  
**Format:** The date by which this skill should be reviewed for continued accuracy and relevance.

```yaml
review_due: 2026-10-16
```

**Purpose:** Skills go stale. A skill that encoded accurate pricing in April 2026 may be wrong by October 2026. A skill encoding regulatory requirements may be superseded by new rules. The `review_due` field makes the review obligation explicit in the skill file rather than relying on the library health checker or an external calendar.

**Recommended review cadence:**

| Skill type | Suggested review interval |
|------------|--------------------------|
| Pricing, rates, commercial terms | 6 months |
| Brand and messaging | 12 months |
| Regulatory and compliance | As required by regulation, or 6 months |
| Delivery methodology | 12 months |
| General knowledge and operations | 12 months |

**In Maestro:** The library health checker surfaces skills where `review_due` is past or within 30 days. The owner receives a notification. Review does not block the skill from operating – a skill past its review date remains active unless manually deactivated.

**Governance note:** `review_due` is optional but strongly recommended for any skill encoding facts that change over time: pricing, regulatory requirements, personnel details, product capabilities. Omitting it from these skills is an accepted risk, not a compliance failure – but it should be a conscious decision, not an oversight.

---

### `classification`

**Type:** string – one of `public`, `internal`, `confidential`, `secret`  
**Required in:** v0.2  
**Default when absent:** `internal`

```yaml
classification: confidential
```

**Classification definitions (ISO 27001 A.8.2):**

| Value | Meaning | LLM routing |
|-------|---------|-------------|
| `public` | The skill's content could be published without harm. Generic methodology, publicly available information, general brand positioning. | Cloud or local, per organisation default. |
| `internal` | The skill's content is for internal use only. Standard operating procedures, internal pricing, delivery standards. Not sensitive enough to require local-only processing, but not appropriate for external disclosure. | Cloud or local, per organisation default. |
| `confidential` | The skill's content is sensitive. Specific client information, commercially sensitive pricing, legal matters, personally identifiable information, regulatory submissions. | **Local model only.** A query that fires a `confidential` skill must never be routed to a cloud LLM, regardless of the organisation's default routing setting. Hard constraint, not configurable. |
| `secret` | Highest sensitivity. Board-level decisions, M&A activity, regulatory investigations, material non-public information. | **Sensitive tier only.** Requires a dedicated, network-isolated LLM endpoint. If sensitive tier is not configured, the query is declined. |

**The classification field governs LLM routing** – its most consequential function. A runtime receiving a `confidential`-classified skill in the context API response must route the entire query to the local model – not just the skill body, but the full query and response. If no local model is configured and a `confidential` skill fires, the runtime must decline to process the query and return a configuration error to the user.

**Classification is conservative by default.** When `classification` is absent from a v0.1.0 skill file, loaders and runtimes should treat it as `internal`. Existing skill files without classification will not trigger `confidential` routing behaviour, which is the correct safe default for skills that predate the field.

**Classification does not control access.** The `classification` field governs LLM routing and audit handling. It does not control who can read or edit the skill file. Access control is managed by the `access_classification` field and the Maestro governance layer.

---

### `access_classification`

**Type:** string – one of `unrestricted`, `restricted`, `classified`  
**Required in:** Optional (v0.1.3+)  
**Default when absent:** `unrestricted`

```yaml
access_classification: restricted
```

**Access classification definitions (ISO 27001 A.9.1):**

| Value | Meaning |
|-------|---------|
| `unrestricted` | Any authenticated user can access this skill. |
| `restricted` | Access limited to defined departments or groups. |
| `classified` | Access restricted to specific authorised roles or named individuals. |

**Relationship to `classification`:** The `classification` field (A.8.2) governs how data is handled — LLM routing, disclosure notices, audit treatment. The `access_classification` field (A.9.1) governs who can access the data. These are orthogonal concerns. A skill can be `internal` classification (routed to cloud) but `restricted` access (only certain teams see it).

---

## Updated schema

The complete v0.1.3 frontmatter schema, showing all fields including those inherited from v0.1.0:

```yaml
---
# Score format version (required, v0.1.2)
score_version: "0.1"

# Identity (required)
name: skill-name                          # kebab-case, unique across library
description: One sentence. Ends with a full stop.
version: 0.1.0                            # semver, increment on every change
owner: name@example.com                   # person responsible for this skill

# Activation (required)
triggers:                                 # 2–10 phrases
  - trigger phrase one
  - trigger phrase two

# Organisation (required)
tags:                                     # from approved vocabulary
  - operations
active: true                              # boolean

# Dates (required)
created: 2026-04-16                       # ISO 8601, set once, never change
updated: 2026-04-16                       # ISO 8601, update on every change

# Governance metadata (optional in v0.1.4, required in v0.2)
approved_by: name@example.com            # named individual, not a team
approved_at: 2026-04-16                  # must be >= updated date
review_due: 2026-10-16                   # recommended, not required
classification: internal                 # public | internal | confidential | secret (ISO 27001 A.8.2)
access_classification: unrestricted      # unrestricted | restricted | classified (ISO 27001 A.9.1) — optional

# Execution hints (optional)
locks_session: false
lock_release_signals: []
cancel_phrases: []
---
```

---

## Validation rules

The following validation rules apply to the governance metadata fields. These are enforced by score-core's validator and surfaced as warnings in v0.1.4, errors in v0.2.

| Rule | Level in v0.1.4 | Level in v0.2 |
|------|----------------|---------------|
| `approved_by` present | Warning if absent | Error |
| `approved_at` present | Warning if absent | Error |
| `classification` present | Warning if absent | Error |
| `approved_at` is a valid ISO 8601 date | Error if present and invalid | Error |
| `approved_at` >= `updated` | Error if present and violated | Error |
| `review_due` is a valid ISO 8601 date | Error if present and invalid | Error |
| `review_due` >= `approved_at` | Warning if present and violated | Warning |
| `review_due` is in the past | Warning | Warning |
| `classification` is one of `public`, `internal`, `confidential`, `secret` | Error if present and invalid | Error |
| `access_classification` is one of `unrestricted`, `restricted`, `classified` | Error if present and invalid | Error |
| `approved_by` is not a team name or role title | Warning (heuristic) | Warning (heuristic) |

**On the approver heuristic:** The validator will warn if `approved_by` appears to be a role title or team name rather than an individual identifier. Common patterns flagged: values containing only generic words such as `team`, `group`, `committee`, `board`, `admin`, `system`. A heuristic: it will produce false positives and false negatives. The governance principle is that a named individual must be accountable; the validator assists but cannot enforce this definitively.

---

## Classification and LLM routing

The `classification` field is the bridge between the skill format and the runtime's LLM routing logic. The full routing behaviour is specified in the Context API specification. This section summarises the skill-level implications.

**Routing matrix:**

| Classification | Default routing | Override possible? |
|---------------|----------------|-------------------|
| `public` | Per org default (cloud or local) | Yes – org can force local |
| `internal` | Per org default (cloud or local) | Yes – org can force local |
| `confidential` | Local only | No – hard constraint |
| `secret` | Sensitive tier only | No – hard constraint. Declined if sensitive tier not configured. |

**Multi-skill queries:** If a query fires multiple skills with different classifications, the most restrictive classification governs routing. A query that fires one `public` skill and one `confidential` skill routes to local only.

**Absent classification:** Treated as `internal`. Routed per organisation default. The conservative safe default: a skill without explicit classification is never forced to cloud routing.

**Runtime behaviour when local model unavailable:** If a `confidential` skill fires and no local model is configured, the runtime must:

1. Not call any LLM.
2. Return a configuration error to the user: something to the effect of "This query requires local processing. Please contact your administrator."
3. Write a `context_api_error` event to The Recording with a note that the query could not be processed due to a routing configuration gap.
4. Not fall through to the cloud model under any circumstances.

---

## Migration from v0.1.0

No migration is required. Existing v0.1.0 skill files are valid v0.1.4 files. The governance metadata fields are additive – no existing field has been modified, renamed, or removed.

**Recommended migration steps for organisations adopting v0.1.4:**

1. Add `classification` to all existing skills first. The highest-priority field: it governs LLM routing, and existing skills without it default to `internal`, which may not be correct for skills containing confidential information.

2. Add `approved_by` and `approved_at` to skills that have already been through a formal approval process. For skills that have not been formally approved, add these fields when the next review or update cycle occurs.

3. Add `review_due` to skills encoding time-sensitive information: pricing, regulatory requirements, personnel details.

**Bulk update:** score-core's CLI provides a helper for bulk-adding governance fields:

```bash
score governance-init ./skills/
```

This command scans the skill library, identifies files missing governance fields, and produces a report. It does not modify files automatically – it outputs a list of files and suggested values (defaulting `classification` to `internal`) for manual review before applying.

---

## Forward compatibility with v0.2

Score v0.2 will make `approved_by`, `approved_at`, and `classification` required fields. `review_due` will remain optional.

The v0.2 validator will reject skill files missing these fields with an error, not a warning. Organisations that have added the fields in v0.1.4 will have no migration work to do when v0.2 is released. Organisations that have not added them will need to do so before upgrading their score-core dependency.

Score v0.2 will also introduce workflow descriptor fields – the schema extension that allows Score files to describe multi-step processes, not just knowledge injection. These will be additive. A v0.1.4 skill file will remain valid as a v0.2 skill file.

The backward compatibility commitment: a skill file valid at any Score version will remain loadable by any future Score-compatible system. We will not remove fields, change their semantics, or alter their validation rules in a breaking way without a major version increment and a documented migration path.

---

## Example skill files

### Minimal v0.1.4 skill (governance fields present, internal classification)

```yaml
---
score_version: "0.1"
name: mw-meeting-prep
description: Prepares the user for client and prospect meetings with agenda, context, and key questions.
version: 0.2.3
owner: mark.goodchild@multipleworks.com.hk
triggers:
  - prep for my meeting
  - meeting prep
  - prepare for my call
  - before my call with
  - briefing for
tags:
  - operations
active: true
created: 2026-04-06
updated: 2026-04-14
approved_by: mark.goodchild@multipleworks.com.hk
approved_at: 2026-04-14
review_due: 2027-04-14
classification: internal
access_classification: unrestricted
---

You are helping the user prepare for an upcoming meeting...
```

### Confidential skill (pricing – local model only)

```yaml
---
score_version: "0.1"
name: mw-rate-and-pricing
description: Provides accurate MultipleWorks rate card information and pricing guidance for engagements.
version: 0.3.1
owner: mark.goodchild@multipleworks.com.hk
triggers:
  - our rates
  - day rate
  - pricing for
  - how much do we charge
  - engagement fees
tags:
  - pricing
active: true
created: 2026-04-06
updated: 2026-04-10
approved_by: mark.goodchild@multipleworks.com.hk
approved_at: 2026-04-10
review_due: 2026-10-10
classification: confidential
access_classification: classified
---

MultipleWorks rate card and pricing guidance...
```

### Public skill (generic methodology – no routing restriction)

```yaml
---
score_version: "0.1"
name: research-synthesis
description: Synthesises research findings into a structured summary with a clear bottom line.
version: 0.1.2
owner: mark.goodchild@multipleworks.com.hk
triggers:
  - synthesise this research
  - summarise these findings
  - pull this together
  - research summary
  - key findings from
tags:
  - research
active: true
created: 2026-04-06
updated: 2026-04-08
approved_by: mark.goodchild@multipleworks.com.hk
approved_at: 2026-04-08
review_due: 2027-04-08
classification: public               # ISO 27001 A.8.2 — no routing restriction
access_classification: unrestricted  # ISO 27001 A.9.1 — any authenticated user
---

Extract key themes, surface tensions or contradictions...
```

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 0.1.4 | 2026-04-22 | Corrected body-text references from `v0.1.1` to `v0.1.4` — governance metadata landed in main Score spec 0.1.4, not 0.1.1 as previously written. This doc's own changelog rows retain their historical version column (0.1.0–0.1.3) since they record this document's independent publishing history. No semantic or schema changes. |
| 0.1.3 | April 2026 | Added R24: valid classification combination matrix. Six valid pairs defined, six invalid combinations documented with reasons. `internal` + `classified` flagged as warning rather than error. |
| 0.1.2 | April 2026 | Updated `classification` to four-level ISO 27001 A.8.2 vocabulary: `public`, `internal`, `confidential`, `secret`. Added `access_classification` field (ISO 27001 A.9.1): `unrestricted`, `restricted`, `classified`. Added organisational vocabulary mapping mechanism. Added disclosure obligation for confidential and secret skills. |
| 0.1.1 | April 2026 | Added governance metadata fields: `approved_by`, `approved_at`, `review_due`, `classification`. All optional. Validation rules established for v0.1.4 (warnings) and v0.2 (errors). |
| 0.1.0 | April 2026 | Initial Score format specification. |
