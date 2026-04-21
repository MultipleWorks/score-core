"""The Recording — Score audit log format v0.1.0.

Pydantic models and hash-chain utilities for the immutable execution
audit log specified in `docs/score_recording_spec.md`.

This module provides:
  - `RecordingEntry` — the per-event record shape
  - `compute_entry_hash()` — canonical hash computation
  - `write_entry()` / `read_entries()` — NDJSON I/O
  - `verify_recording_file()` — chain integrity verification

The runtime is responsible for generating `event_id`, `previous_hash`,
and `entry_hash` at write time. This module provides the primitives —
not an opinionated writer class, since Recording storage varies by
deployment (local NDJSON file, S3 Object Lock, HSM-signed stream, etc).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


SCHEMA_VERSION = "0.1.0"
GENESIS_HASH = "0" * 64  # "previous_hash" for the first entry of a day


EventType = Literal[
    "query_executed",
    "honesty_protocol_fired",
    "session_locked",
    "session_released",
    "session_cancelled",
    "context_api_error",
    "runtime_started",
    "runtime_stopped",
    "skill_version_changed",
]

DetailLevel = Literal["minimal", "full"]

Interface = Literal["telegram", "slack", "teams", "api", "web", "mcp"]

LLMRoutedTo = Literal["local", "cloud", "none"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SkillVersionRef(BaseModel):
    """Name + version of a skill recorded in a Recording entry.

    The same shape as the Context API's SkillVersionRef, re-declared here
    so `score.recording` does not depend on `score.context_api` for
    implementations that only need audit logging.
    """
    name: str
    version: str


class SkillBody(BaseModel):
    """Full skill body captured in a `detail_level: full` Recording entry.

    Present only when `detail_level` is `"full"`. Regulated-industry
    deployments use this to prove exactly what content governed a
    response, not just the skill version.
    """
    name: str
    version: str
    body: str


class RecordingEntry(BaseModel):
    """A single execution event recorded in The Recording.

    All fields from the minimal detail level are required. Fields marked
    "full only" below are populated when `detail_level == "full"`; at
    minimal level they are absent from the serialised JSON.

    The runtime is responsible for populating `previous_hash` (the
    entry_hash of the preceding entry, or GENESIS_HASH for the first
    entry of a day) and `entry_hash` (computed via `compute_entry_hash`).
    """
    schema_version: str = SCHEMA_VERSION
    event_id: str
    event_type: EventType
    detail_level: DetailLevel
    timestamp: datetime
    request_id: str
    session_id: Optional[str] = None
    interface: Interface
    user_id: Optional[str] = None
    query_hash: str
    matched: bool
    gap_logged: bool
    skill_versions: list[SkillVersionRef] = Field(default_factory=list)
    llm_routed_to: LLMRoutedTo
    honesty_protocol_fired: bool
    classification_applied: Optional[str] = None
    disclosure_appended: bool = False
    previous_hash: str
    entry_hash: str

    # Full detail level — optional at the model level, required when
    # detail_level == "full". Validation of that constraint is left to
    # the runtime that writes Recording entries; both shapes are valid
    # Pydantic objects so existing entries can be loaded regardless.
    query: Optional[str] = None
    response: Optional[str] = None
    system_prompt_hash: Optional[str] = None
    skill_bodies: Optional[list[SkillBody]] = None


# ---------------------------------------------------------------------------
# Hash utilities
# ---------------------------------------------------------------------------

def compute_entry_hash(entry: dict, previous_hash: str) -> str:
    """Compute the canonical entry_hash for a Recording entry.

    The entry is serialised with sorted keys and no whitespace, the
    `entry_hash` field is excluded, and the result is concatenated with
    the previous entry's hash before SHA-256 hashing. This exact
    serialisation is required for chain verification — it must be
    identical across every runtime implementing the Recording spec.

    Args:
        entry: The full entry dict INCLUDING entry_hash (it will be
            stripped). If you pass an entry without entry_hash set,
            that's also fine.
        previous_hash: The entry_hash of the preceding entry, or
            GENESIS_HASH for the first entry of a day.

    Returns:
        SHA-256 hex digest (64 characters, lowercase).
    """
    entry_without_hash = {k: v for k, v in entry.items() if k != "entry_hash"}
    content = json.dumps(
        entry_without_hash,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    to_hash = content + previous_hash
    return hashlib.sha256(to_hash.encode("utf-8")).hexdigest()


def query_hash(query: str) -> str:
    """SHA-256 hex digest of a query string. Used to populate
    `query_hash` in both Context API audit and Recording entries.
    """
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _json_default(obj):
    """Fallback serialiser for types the stdlib JSON encoder rejects.
    Used by compute_entry_hash so datetime values in entries hash
    deterministically.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):  # Pydantic model
        return obj.model_dump(mode="json")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def write_entry(entry: RecordingEntry, file_path: str) -> None:
    """Append a single entry to a Recording NDJSON file.

    Opens in append mode so existing entries are never modified.
    Serialisation uses sorted keys + no whitespace — the same canonical
    form used for hash computation, so the hash in a read entry matches
    the hash computed over the file content.

    Does NOT compute or verify the entry_hash — callers must set it
    before calling. See `compute_entry_hash`.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        entry.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_entries(file_path: str):
    """Yield RecordingEntry objects from an NDJSON Recording file.

    Generator — does not load the full file into memory. Raises
    json.JSONDecodeError if any line is malformed (do not silently skip —
    a malformed line means tamper or corruption).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            yield RecordingEntry(**data)


def verify_recording_file(file_path: str) -> tuple[bool, Optional[str]]:
    """Verify the hash chain of a Recording NDJSON file.

    Recomputes entry_hash for every line and checks it matches the stored
    value and the previous_hash of the following entry. Returns:
        (True, None) — chain is intact
        (False, reason) — chain is broken; reason describes where and how

    The first entry's previous_hash should be GENESIS_HASH for the first
    Recording file ever written, or the entry_hash of the last entry in
    the previous day's file. This function checks only intra-file chain
    integrity — cross-file verification is a caller-level concern.
    """
    previous_hash = GENESIS_HASH
    first = True
    with open(file_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                return False, f"line {line_number}: malformed JSON — {e}"

            claimed_hash = entry.get("entry_hash")
            if claimed_hash is None:
                return False, f"line {line_number}: missing entry_hash"

            if first:
                # The first entry can chain from anywhere — accept whatever
                # previous_hash it declares as the baseline for the chain.
                previous_hash = entry.get("previous_hash", GENESIS_HASH)
                first = False
            else:
                if entry.get("previous_hash") != previous_hash:
                    return False, (
                        f"line {line_number}: previous_hash "
                        f"{entry.get('previous_hash')!r} does not match prior "
                        f"entry's entry_hash {previous_hash!r}"
                    )

            computed = compute_entry_hash(entry, previous_hash)
            if computed != claimed_hash:
                return False, (
                    f"line {line_number}: entry_hash mismatch — "
                    f"claimed {claimed_hash}, computed {computed}"
                )
            previous_hash = claimed_hash

    return True, None
