# The Recording
## Score Audit Log Format Specification v0.1.0

**Status:** Draft — specification complete, reference implementation in development.
**Author:** Mark Goodchild, MultipleWorks  
**Repository:** github.com/multipleworks/score  
**Last updated:** April 2026

---

## Contents

- [Overview](#overview)
- [Design principles](#design-principles)
- [Format](#format)
- [Event record schema](#event-record-schema)
- [Detail levels](#detail-levels)
  - [Minimal](#minimal-default)
  - [Full](#full-regulated-industries)
- [Event types](#event-types)
- [Storage requirements](#storage-requirements)
- [Tamper evidence](#tamper-evidence)
- [Portability](#portability)
- [The Independent Review](#the-independent-review)
- [Relationship to the context API](#relationship-to-the-context-api)
- [Changelog](#changelog)

---

## Overview

The Recording is the immutable audit log of a Score runtime. Every execution event – every query received, every skill invoked, every honesty protocol activation, every session lock – is written to The Recording at the moment it occurs.

The Recording has two audiences: the organisation that operates the runtime, and an external reviewer – an auditor, a regulator, or legal counsel – who needs to verify that the runtime behaved as declared.

For an external reviewer, The Recording is evidence. The published Score files are the declaration. The Independent Review is the process of comparing the two. The Recording must be structured and portable enough that this comparison can be performed without any Maestro tooling, without access to the runtime, and without cooperation from the organisation's IT team beyond providing the log files.

This document defines the format, the storage requirements, the tamper evidence model, and what an Independent Review examines.

---

## Design principles

**Written at execution time, never after.** Recording entries are written by the runtime at the moment of execution, before the response is returned to the user. An entry cannot be created retrospectively. The management layer does not write to The Recording – only the runtime does.

**Owned by the organisation.** The Recording is stored on the organisation's own infrastructure. It is not transmitted to MultipleWorks, to Maestro, or to any third party. The organisation controls where it lives, who can read it, and how long it is retained.

**Readable without tooling.** The format is newline-delimited JSON (NDJSON). Any text editor, any `jq` command, any spreadsheet import, and any audit tool can read it. An external reviewer does not need Maestro, does not need the runtime, and does not need any Score-specific software to examine The Recording.

**Minimal by default, full when required.** The default detail level stores metadata and query hashes only – no raw queries, no raw responses. Organisations in regulated industries that require full content logging can configure `detail_level: full`. Both levels use the same schema.

**Tamper-evident, not tamper-proof.** The Recording uses chained SHA-256 hashes to make tampering detectable. It does not use a distributed ledger or cryptographic signing infrastructure. Tamper evidence means an auditor can determine whether The Recording has been altered – it does not prevent alteration by someone with direct filesystem access. Organisations requiring stronger guarantees should write The Recording to append-only storage.

**One file per day.** Recording files are named by UTC date. This keeps individual files to a manageable size, keeps retention policy simple, and gives an external reviewer a clear scope when asked to examine a specific period.

---

## Format

The Recording is stored as newline-delimited JSON (NDJSON). Each line is a complete, self-contained JSON object representing one execution event. Lines are written in strict chronological order. The file is append-only – existing lines are never modified or deleted.

**File naming:**

```
recording-YYYY-MM-DD.ndjson
```

**File location:** Configurable. Default is `./data/recording/` relative to the runtime's working directory.

**Encoding:** UTF-8. No BOM.

**Line endings:** LF (`\n`). No CRLF.

**Example file path:**

```
./data/recording/recording-2026-04-16.ndjson
```

**Example file contents (two events, minimal detail level):**

```
{"schema_version":"0.1.0","event_id":"evt_a3f9b2c1","event_type":"query_executed","detail_level":"minimal","timestamp":"2026-04-16T09:14:33Z","request_id":"req_7f2a1b9d","session_id":"sess_a3f9b2c1","interface":"telegram","user_id":"usr_4821","query_hash":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","matched":true,"gap_logged":false,"skill_versions":[{"name":"mw-proposal-review","version":"0.2.1"},{"name":"mw-brand","version":"0.1.4"}],"llm_routed_to":"cloud","honesty_protocol_fired":false,"previous_hash":"0000000000000000000000000000000000000000000000000000000000000000","entry_hash":"a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"}
{"schema_version":"0.1.0","event_id":"evt_b4c8d3e2","event_type":"honesty_protocol_fired","detail_level":"minimal","timestamp":"2026-04-16T09:31:07Z","request_id":"req_8g3b2c0e","session_id":null,"interface":"telegram","user_id":"usr_4821","query_hash":"f4c9d55309fd2c250bgcg5d9aa7bc03528bf52eccdb935dc495002c8963c3966","matched":false,"gap_logged":true,"skill_versions":[],"llm_routed_to":"none","honesty_protocol_fired":true,"previous_hash":"a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2","entry_hash":"c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"}
```

---

## Event record schema

Every Recording entry – regardless of detail level or event type – contains these fields:

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | The Recording format version. Used by audit tools to parse correctly. |
| `event_id` | string | A unique identifier for this event. Generated by the runtime. Format: `evt_` followed by 8 random alphanumeric characters. |
| `event_type` | string | What happened. See [Event types](#event-types). |
| `detail_level` | string | `minimal` or `full`. Determines which optional fields are present. |
| `timestamp` | string | ISO 8601 UTC timestamp of when the event occurred. Written at execution time, before the response is returned. |
| `request_id` | string | The `request_id` returned by the context API for this execution. Links the Recording entry to the management layer's own audit records. |
| `session_id` | string or null | The session identifier, if the query was part of a multi-turn conversation. Null for single-turn queries. |
| `interface` | string | The interface through which the query arrived. One of: `telegram`, `slack`, `teams`, `api`, `web`. |
| `user_id` | string or null | Opaque identifier for the end user, as provided in the context API request. Never a name or email address. |
| `query_hash` | string | SHA-256 hash of the raw query string. Allows verification against the runtime's own logs without storing the query in The Recording. |
| `matched` | boolean | Whether one or more skills fired for this query. |
| `gap_logged` | boolean | Whether the query triggered the honesty protocol (organisational signal, no matching skills). |
| `skill_versions` | array | Array of `{name, version}` objects for every skill that fired. Empty array if no skills matched. |
| `llm_routed_to` | string | Where the query was sent for LLM processing. One of: `local`, `cloud`, `none`. `none` when the honesty protocol fired or the query was handled without an LLM call. |
| `honesty_protocol_fired` | boolean | Whether the honesty protocol returned a refusal message for this query. |
| `previous_hash` | string | The `entry_hash` of the immediately preceding entry in the file. The first entry of each day uses the SHA-256 hash of the previous day's filename (or 64 zeros for the first Recording entry ever written). |
| `entry_hash` | string | SHA-256 hash of this entry's content, excluding the `entry_hash` field itself, concatenated with `previous_hash`. Used to detect tampering. |

---

## Detail levels

### Minimal (default)

The minimal detail level stores metadata and hashes only. No raw query text. No raw response text. The correct default for most deployments: full auditability of execution behaviour without creating a content store of user queries.

An Independent Reviewer working with minimal Recording files can verify:

- Which skills governed which queries, and at what exact version.
- Whether the honesty protocol fired, and when.
- LLM routing decisions – local versus cloud.
- Session continuity across multi-turn conversations.
- The chronological integrity of The Recording via the hash chain.

They cannot verify the content of individual queries or responses from The Recording alone. For content verification, the runtime's application logs (stored separately) must be cross-referenced using the `request_id` as the join key.

### Full (regulated industries)

The full detail level adds raw query and response content to each entry. It is appropriate for organisations in regulated industries where a regulator or auditor requires the ability to examine the content of AI-generated responses, not just the metadata of execution events.

**Additional fields at `detail_level: full`:**

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | The raw query text, as received by the runtime. |
| `response` | string | The raw response text, as returned to the user. |
| `system_prompt_hash` | string | SHA-256 hash of the assembled system prompt (concatenated skill bodies) sent to the LLM. Allows verification that the correct skill content was used without storing the full prompt. |
| `skill_bodies` | array or null | Array of `{name, version, body}` objects containing the full text of each skill body injected for this query. Null if `matched` is false. Present only at `detail_level: full` because it significantly increases file size. |

**Storage note:** Full detail level Recording files are substantially larger than minimal files. A deployment handling 1,000 queries per day with average query and response lengths of 200 words each should expect Recording files of approximately 5–10 MB per day. Plan retention and storage accordingly.

**Configuration:** Detail level is set in the runtime configuration, not in the Score file. It applies to all Recording entries from that runtime instance. It cannot be changed mid-session.

---

## Event types

| Event type | When it is written |
|------------|-------------------|
| `query_executed` | A query was received, the context API was called, and a response was returned. The standard event for every user interaction. |
| `honesty_protocol_fired` | The context API returned `gap_logged: true`. The runtime returned the configured refusal message. No LLM was called. |
| `session_locked` | A skill with `locks_session: true` fired and the runtime entered session-lock mode. |
| `session_released` | A lock release signal was detected and the runtime exited session-lock mode normally. |
| `session_cancelled` | A cancel phrase was detected and the runtime exited session-lock mode without completing the locked flow. |
| `context_api_error` | The context API returned an error response. The query was not processed. Includes the HTTP status code and error code in the entry. |
| `runtime_started` | The runtime completed its startup sequence and is ready to accept queries. Includes runtime version, Score version from config, and org_id. |
| `runtime_stopped` | The runtime received a shutdown signal and stopped cleanly. |
| `skill_version_changed` | The context API returned a different version of a skill than was returned in the immediately preceding call. The new and previous versions are both logged. |

---

## Storage requirements

**Append-only.** The runtime opens Recording files in append mode. It never overwrites or truncates an existing file. Write failures must be logged to a separate error log and must not silently drop Recording entries – if The Recording cannot be written, the runtime should halt query processing and alert the operator.

**Separate from application logs.** The Recording is a distinct set of files from the runtime's application and error logs. They serve different purposes and have different audiences. Do not commingle them.

**Retention policy.** The Recording must be retained for at minimum the period specified by the organisation's data governance policy. In the absence of a specific policy, the recommended minimum is 12 months. For regulated industries, follow the applicable regulatory requirement – financial services in most jurisdictions require a minimum of 5–7 years.

**Access control.** Read access to Recording files should be restricted to: the runtime process (write), system administrators, compliance officers, and authorised auditors. Write access must be restricted to the runtime process only. No human should have write access to Recording files in a production environment.

**Backup.** Recording files must be included in the organisation's standard backup procedures. A Recording that exists only on the runtime's local disk is not an audit log – it is a single point of failure.

**Rotation.** Files rotate at UTC midnight. The runtime creates a new file at the start of each day. Old files are never modified after rotation.

---

## Tamper evidence

The Recording uses a chained hash structure to make tampering detectable. Each entry contains the hash of the previous entry. An auditor can verify the chain by recomputing hashes forward from the first entry – any modification to any entry, or any deletion of an entry, breaks the chain at that point.

**Hash computation:**

```python
import hashlib, json

def compute_entry_hash(entry: dict, previous_hash: str) -> str:
    # Remove entry_hash from the entry before hashing
    entry_without_hash = {k: v for k, v in entry.items() if k != 'entry_hash'}
    # Serialise deterministically: sorted keys, no whitespace
    content = json.dumps(entry_without_hash, sort_keys=True, separators=(',', ':'))
    # Concatenate with previous hash
    to_hash = content + previous_hash
    return hashlib.sha256(to_hash.encode('utf-8')).hexdigest()
```

**Verification:**

```python
def verify_recording_file(filepath: str) -> bool:
    previous_hash = '0' * 64  # Reset at start of each file
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_number, line in enumerate(f, 1):
            entry = json.loads(line.strip())
            claimed_hash = entry.get('entry_hash')
            computed_hash = compute_entry_hash(entry, previous_hash)
            if claimed_hash != computed_hash:
                print(f"Chain broken at line {line_number}")
                return False
            previous_hash = claimed_hash
    return True
```

**Limitations:** The hash chain detects tampering but does not prevent it. An attacker with write access to Recording files could recompute the entire chain after modification and produce a valid-looking but falsified Recording. Organisations requiring stronger guarantees should:

- Write Recording files to append-only storage (AWS S3 Object Lock, Azure Immutable Blob Storage, or equivalent).
- Use a write-once logging service that provides independent tamper evidence.
- Have the runtime sign each entry with a private key held in a hardware security module.

These stronger guarantees are outside the scope of this specification but are recommended for financial services and other regulated environments where Recording integrity is subject to regulatory scrutiny.

---

## Portability

The Recording is designed to be examined by any party with the following:

- A UTF-8 text reader.
- A JSON parser.
- The Score format specification (to understand skill names and versions).
- The published Score files for the organisation (to verify what each skill version contained).

No Maestro tooling. No Score-specific software. No runtime access.

**What an auditor receives:**

1. The Recording files (NDJSON) for the period under review.
2. The published Score files – or the git history of the skill library – covering the same period. Allows the auditor to retrieve the exact content of every skill version referenced in the Recording.
3. The `request_id` linkage to the management layer's own context API logs, if cross-referencing is required.

**What an auditor can determine from the Recording alone:**

- Every query that was processed, identified by hash.
- Every skill that governed each response, at exact version.
- Every instance where the honesty protocol fired.
- Every LLM routing decision.
- Every session lock, release, and cancellation.
- The chronological integrity of the log.
- Whether any entries have been tampered with or deleted.

**What requires cross-referencing with other sources:**

- The content of individual queries and responses (application logs, cross-referenced by `request_id` – or inline in `full` detail level).
- The full text of skill bodies at specific versions (the skill library git history).

---

## The Independent Review

The Independent Review is a formal examination of The Recording against the organisation's published Score. It answers one question: did the runtime behave as the organisation declared it would?

The declared standard is the published Score – the set of approved skill files, with their triggers, their bodies, and their version histories. The evidence of execution is The Recording. The comparison is the review.

**What an Independent Reviewer examines:**

1. **Skill coverage:** For every `query_executed` event where `matched` is true, does the response claim to have used skills that exist in the published Score at the versions recorded? Cross-reference `skill_versions` in the Recording against the skill library git history.

2. **Honesty protocol compliance:** For every `honesty_protocol_fired` event, was the runtime operating without skills when it should have been? This catches cases where a skill may have been temporarily deactivated without proper governance.

3. **LLM routing compliance:** For every `query_executed` event, does `llm_routed_to` match the routing rules the organisation declared? `confidential`-classified skills must always show `local`. Any `cloud` routing for a query where a `confidential` skill fired is a compliance finding.

4. **Chain integrity:** Is the hash chain unbroken across the entire review period? Any break is a finding requiring explanation.

5. **Gap log review:** Are the `honesty_protocol_fired` events consistent with the skill library's coverage? A high volume of honesty protocol activations in a domain where skills exist may indicate trigger phrase gaps or skill deactivation without proper governance.

6. **Version consistency:** Did skill versions change during the review period? `skill_version_changed` events should correspond to approved updates in the skill library's git history. An unexplained version change is a finding.

**What the Independent Review is not:**

The Independent Review is not a content review of AI-generated responses. It does not assess whether responses were accurate, appropriate, or helpful – only whether the runtime was operating within its declared governance framework at the time they were generated.

Content review, if required, is a separate exercise using the `full` detail level Recording or the application logs.

---

## Relationship to the context API

The Recording and the context API are complementary. The context API generates a `request_id` for every call. The Recording stores that `request_id` in every entry. This creates a verifiable link between:

- The management layer's record of which skills were approved and served (context API logs).
- The runtime's record of how those skills were used in execution (The Recording).

An auditor who has access to both can verify end-to-end: the management layer served version `0.2.1` of `mw-proposal-review` in response to context request `req_7f2a1b9d`, and the runtime recorded using that skill in Recording entry `evt_a3f9b2c1` for the same `request_id`. The chain is complete.

The management layer's context API logs are not part of The Recording. They are a separate audit trail maintained by Maestro (or whichever management layer the organisation uses). This specification covers only the runtime's Recording.

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 0.1.0 | April 2026 | Initial specification. |
