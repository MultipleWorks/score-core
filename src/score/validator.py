"""Score v0.1.1 strict validator (three-tier).

Validates a skill payload (dict, not SkillFile — payloads from API write
flows may be incomplete while a user is mid-edit) against the rules in
`score_spec.md`. Returns errors (blocking), warnings (advisory), and
hints (quality guidance).

Two public interfaces:
  - `validate_skill(payload, is_update) -> dict` — dict-in, dict-out.
    Canonical interface used by the Maestro API. Never raises.
  - `validate_skill_file(skill_file) -> ValidationResult` — Pydantic-in,
    dataclass-out. Preferred for external consumers working with SkillFile
    objects directly.

Both interfaces run the same underlying rule set. If a rule fires on one
it fires on the other.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from score.schema import (
    ACCESS_CLASSIFICATIONS,
    APPROVED_TAGS,
    BODY_HINT_WORDS,
    BODY_SPARSE_WORDS,
    BODY_WARNING_WORDS,
    CLASSIFICATIONS,
    MAX_TRIGGERS,
    MIN_TRIGGERS,
    REFERENCE_TAGS,
    SkillFile,
    ValidationResult,
)

_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Matches `. X` or `? X` where X is uppercase — signals a second sentence.
_MULTI_SENTENCE_RE = re.compile(r'[.?!]\s+[A-Z]')

VAGUE_VERBS = {"helps", "assists", "supports", "enables"}
FIRST_PERSON = {" i ", " i'", " i'm", " i will", " i've", " we ", " we're",
                " we'll", " we've", " my ", " our ", " us "}
CONVERSATIONAL_CUES = {"can you", "help me", "how do i", "could you",
                       "please", "i need", "for me", "show me"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_iso_date(value) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _issue(field: str, message: str) -> dict:
    return {"field": field, "message": message}


def _word_count(text: str) -> int:
    return len(text.split())


def _has_structure(text: str) -> bool:
    """True if the body has any markdown headings, bullets, or numbered lists."""
    for line in text.splitlines():
        s = line.lstrip()
        if s.startswith("#") or s.startswith("- ") or s.startswith("* "):
            return True
        if re.match(r"^\d+\.\s", s):
            return True
    return False


# ---------------------------------------------------------------------------
# Error checks (blocking)
# ---------------------------------------------------------------------------

def _check_errors(payload: dict) -> list[dict]:
    errors: list[dict] = []

    required = {"name", "description", "version", "owner", "triggers",
                "tags", "active", "created", "updated", "body"}
    missing = required - set(payload.keys())
    for f in sorted(missing):
        errors.append(_issue(f, "required field is missing"))
    if missing:
        return errors  # further checks would raise KeyErrors

    # name
    name = payload["name"]
    if not isinstance(name, str) or not name:
        errors.append(_issue("name", "must be a non-empty string"))
    elif not _KEBAB_RE.match(name):
        errors.append(_issue(
            "name",
            "must be kebab-case (lowercase letters, digits, hyphens only)",
        ))

    # description
    desc = payload["description"]
    if not isinstance(desc, str) or not desc.strip():
        errors.append(_issue("description", "must be a non-empty string"))
    else:
        if "\n" in desc:
            errors.append(_issue("description", "must not contain line breaks"))
        elif _MULTI_SENTENCE_RE.search(desc):
            errors.append(_issue(
                "description",
                "must be a single sentence — split at the full stop or merge into one sentence",
            ))
        elif not desc.rstrip().endswith("."):
            errors.append(_issue(
                "description",
                "must be a single sentence ending with a full stop",
            ))

    # version
    ver = payload["version"]
    if not isinstance(ver, str) or not _SEMVER_RE.match(ver):
        errors.append(_issue("version", "must be semver x.y.z (all integers)"))

    # owner
    owner = payload["owner"]
    if not isinstance(owner, str) or not owner.strip():
        errors.append(_issue("owner", "must be a non-empty string"))

    # triggers
    triggers = payload["triggers"]
    if not isinstance(triggers, list):
        errors.append(_issue("triggers", "must be a list of strings"))
    else:
        if len(triggers) < MIN_TRIGGERS:
            errors.append(_issue(
                "triggers",
                f"minimum {MIN_TRIGGERS} triggers required (got {len(triggers)})",
            ))
        elif len(triggers) > MAX_TRIGGERS:
            errors.append(_issue(
                "triggers",
                f"maximum {MAX_TRIGGERS} triggers allowed (got {len(triggers)})",
            ))
        for i, t in enumerate(triggers):
            if not isinstance(t, str) or not t.strip():
                errors.append(_issue(f"triggers[{i}]", "must be a non-empty string"))

    # tags
    tags = payload["tags"]
    if not isinstance(tags, list):
        errors.append(_issue("tags", "must be a list of strings"))
    else:
        for i, tag in enumerate(tags):
            if not isinstance(tag, str):
                errors.append(_issue(f"tags[{i}]", "must be a string"))
            elif tag not in APPROVED_TAGS:
                approved = ", ".join(sorted(APPROVED_TAGS))
                errors.append(_issue(
                    f"tags[{i}]",
                    f"invalid tag '{tag}'. Approved: {approved}",
                ))

    # active
    if not isinstance(payload["active"], bool):
        errors.append(_issue(
            "active", "must be boolean true or false, not a string",
        ))

    # created, updated
    created = _parse_iso_date(payload["created"])
    if created is None:
        errors.append(_issue("created", "must be ISO 8601 date (YYYY-MM-DD)"))
    updated = _parse_iso_date(payload["updated"])
    if updated is None:
        errors.append(_issue("updated", "must be ISO 8601 date (YYYY-MM-DD)"))
    if created is not None and updated is not None and updated < created:
        errors.append(_issue(
            "updated", f"must be >= created ({payload['created']})",
        ))

    # body
    body = payload["body"]
    if not isinstance(body, str) or not body.strip():
        errors.append(_issue("body", "must be a non-empty string"))

    # v0.1.1 governance fields — errors fire only if field is PRESENT and malformed.
    # Missing governance fields are warnings, not errors.
    _check_governance_errors(payload, errors, updated)

    return errors


# ---------------------------------------------------------------------------
# R24 — classification combination validation (v0.1.3)
# ---------------------------------------------------------------------------

VALID_COMBINATIONS = {
    ("public", "unrestricted"),
    ("internal", "unrestricted"),
    ("internal", "restricted"),
    ("confidential", "restricted"),
    ("confidential", "classified"),
    ("secret", "classified"),
}

WARNING_COMBINATIONS = {
    ("internal", "classified"),
}


def validate_classification_combination(
    classification: str | None,
    access_classification: str | None,
) -> tuple[list[str], list[str]]:
    """Validate the combination of classification and access_classification.

    Returns (errors, warnings). Only runs when both fields are present.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not classification or not access_classification:
        return errors, warnings

    pair = (classification, access_classification)

    if pair in WARNING_COMBINATIONS:
        warnings.append(
            f"classification '{classification}' with access_classification "
            f"'{access_classification}' is unusual. Content that warrants "
            f"individual authorisation is likely confidential, not internal. "
            f"Review the classification level."
        )
    elif pair not in VALID_COMBINATIONS:
        if classification == "public":
            errors.append(
                f"classification 'public' cannot be combined with "
                f"access_classification '{access_classification}'. "
                f"Public content is accessible to all by definition — "
                f"use access_classification 'unrestricted'."
            )
        elif access_classification == "unrestricted" and classification in ("confidential", "secret"):
            errors.append(
                f"classification '{classification}' cannot be combined with "
                f"access_classification 'unrestricted'. "
                f"{classification.capitalize()} content must not be accessible "
                f"to all authenticated users."
            )
        elif classification == "secret" and access_classification == "restricted":
            errors.append(
                "classification 'secret' cannot be combined with "
                "access_classification 'restricted'. Secret content "
                "requires individual authorisation — use 'classified'."
            )
        else:
            errors.append(
                f"classification '{classification}' and access_classification "
                f"'{access_classification}' is not a valid combination. "
                f"See score_governance_metadata_spec.md (bundled with score-core; "
                f"also at github.com/multipleworks/score) for the six valid pairs."
            )

    return errors, warnings


def _check_governance_errors(payload: dict, errors: list, updated: Optional[date]) -> None:
    """v0.1.1 governance metadata error rules.

    Only fires when a field is present but has an invalid value. Absence
    of governance fields is a warning in v0.1.1 (will become an error in
    v0.2 once the migration path is complete).
    """
    # approved_at — must be a valid ISO date if present, and must be >= updated
    if "approved_at" in payload and payload["approved_at"] is not None:
        approved_at = _parse_iso_date(payload["approved_at"])
        if approved_at is None:
            errors.append(_issue(
                "approved_at", "must be ISO 8601 date (YYYY-MM-DD)",
            ))
        elif updated is not None and approved_at < updated:
            errors.append(_issue(
                "approved_at",
                f"approval date must be >= updated ({payload['updated']}) — "
                f"the approval applies to the content as at updated date",
            ))

    # review_due — if present must be valid ISO date
    if "review_due" in payload and payload["review_due"] is not None:
        review_due = _parse_iso_date(payload["review_due"])
        if review_due is None:
            errors.append(_issue(
                "review_due", "must be ISO 8601 date (YYYY-MM-DD)",
            ))

    # classification — if present must be one of the allowed values
    if "classification" in payload and payload["classification"] is not None:
        cls = payload["classification"]
        if cls not in CLASSIFICATIONS:
            errors.append(_issue(
                "classification",
                f"must be one of: {', '.join(sorted(CLASSIFICATIONS))}",
            ))

    # access_classification — if present must be one of the allowed values
    if "access_classification" in payload and payload["access_classification"] is not None:
        acc = payload["access_classification"]
        if acc not in ACCESS_CLASSIFICATIONS:
            errors.append(_issue(
                "access_classification",
                f"must be one of: {', '.join(sorted(ACCESS_CLASSIFICATIONS))}",
            ))

    # R24: classification + access_classification combination validation
    combo_errors, combo_warnings = validate_classification_combination(
        payload.get("classification"),
        payload.get("access_classification"),
    )
    for msg in combo_errors:
        errors.append(_issue("classification", msg))


# ---------------------------------------------------------------------------
# Warning checks (advisory — saveable but flagged)
# ---------------------------------------------------------------------------

def _check_warnings(payload: dict, is_update: bool) -> list[dict]:
    warnings: list[dict] = []

    # body approaching 500-word limit
    body = payload.get("body", "")
    if isinstance(body, str):
        wc = _word_count(body)
        if wc > BODY_WARNING_WORDS:
            warnings.append(_issue(
                "body",
                f"body is {wc} words, approaching the 500-word limit",
            ))

    # reference skills need wider trigger surface
    triggers = payload.get("triggers", [])
    tags = payload.get("tags", [])
    if (isinstance(triggers, list) and isinstance(tags, list)
            and any(t in REFERENCE_TAGS for t in tags if isinstance(t, str))
            and len(triggers) < 4):
        warnings.append(_issue(
            "triggers",
            f"only {len(triggers)} trigger(s) on a reference skill. "
            f"Reference skills (brand, pricing) benefit from 8+ triggers for coverage",
        ))

    # Fewer than 3 triggers in general (new in v0.1.1 — spec line)
    if isinstance(triggers, list) and MIN_TRIGGERS <= len(triggers) < 3:
        warnings.append(_issue(
            "triggers",
            f"only {len(triggers)} triggers — 3+ covers more phrasing variants",
        ))

    # updated == created: skill has never been edited after creation.
    # Only warn on updates — a freshly created skill naturally has
    # updated == created, which is the expected initial state.
    if is_update:
        created = _parse_iso_date(payload.get("created"))
        updated = _parse_iso_date(payload.get("updated"))
        if created is not None and updated is not None and created == updated:
            warnings.append(_issue(
                "updated",
                "updated date equals created — skill has not been edited since creation",
            ))

    # missing change_summary on update
    if is_update:
        summary = payload.get("change_summary")
        if not isinstance(summary, str) or not summary.strip():
            warnings.append(_issue(
                "change_summary",
                "no change summary provided — version history will show 'No summary'",
            ))

    # v0.1.1 governance metadata — absent fields are warnings
    _check_governance_warnings(payload, warnings)

    return warnings


def _check_governance_warnings(payload: dict, warnings: list) -> None:
    """v0.1.1 governance fields — warn if absent.

    These become errors in v0.2. The migration path is: add warnings in
    v0.1.1 (now) so skill authors have time to populate them via
    `score migrate`, then flip to errors in the v0.2 bump.
    """
    if not payload.get("approved_by"):
        warnings.append(_issue(
            "approved_by",
            "missing approved_by — required in Score v0.2 (governance). "
            "Run `score migrate --to 0.1.4` to add the placeholder, then "
            "fill in the approver.",
        ))

    if not payload.get("approved_at"):
        warnings.append(_issue(
            "approved_at",
            "missing approved_at — required in Score v0.2 (governance). "
            "Set to the date this version was approved.",
        ))

    if not payload.get("classification"):
        warnings.append(_issue(
            "classification",
            "missing classification — required in Score v0.2. "
            "Use 'public', 'internal', or 'confidential'. "
            "'confidential' routes the skill to local-only LLMs.",
        ))

    # R24 combination warnings (e.g. internal + classified)
    _, combo_warnings = validate_classification_combination(
        payload.get("classification"),
        payload.get("access_classification"),
    )
    for msg in combo_warnings:
        warnings.append(_issue("classification", msg))

    if not payload.get("review_due"):
        warnings.append(_issue(
            "review_due",
            "missing review_due — recommended. Sets a date by which the "
            "skill should be re-reviewed for accuracy.",
        ))
    else:
        review_due = _parse_iso_date(payload["review_due"])
        if review_due is not None and review_due < date.today():
            warnings.append(_issue(
                "review_due",
                f"review_due ({payload['review_due']}) is in the past — "
                f"schedule a review or update the date",
            ))


# ---------------------------------------------------------------------------
# Hint checks (quality guidance — always non-blocking)
# ---------------------------------------------------------------------------

def _check_hints(payload: dict) -> list[dict]:
    hints: list[dict] = []

    body = payload.get("body", "")
    if isinstance(body, str) and body.strip():
        # First-person language in body
        body_lower = " " + body.lower() + " "
        for phrase in FIRST_PERSON:
            if phrase in body_lower:
                hints.append(_issue(
                    "body",
                    'contains first-person language — use second person imperative '
                    'instead: "Review the proposal" not "I will review the proposal"',
                ))
                break

        # Long unstructured body
        wc = _word_count(body)
        if wc > BODY_HINT_WORDS and not _has_structure(body):
            hints.append(_issue(
                "body",
                f"body is {wc} words without headers or bullet points — "
                f"consider structuring for LLM readability",
            ))

        # Sparse body (v0.1.1 new rule)
        if wc < BODY_SPARSE_WORDS:
            hints.append(_issue(
                "body",
                f"body is {wc} words — may be too sparse to be useful. "
                f"Reference skills should be exhaustive on facts; action skills "
                f"should be specific about expected output.",
            ))

    # Description uses vague verbs
    desc = payload.get("description", "")
    if isinstance(desc, str) and desc.strip():
        first_word = desc.strip().split()[0].lower().rstrip(".,")
        if first_word in VAGUE_VERBS:
            hints.append(_issue(
                "description",
                f'description starts with a vague verb ("{first_word}") — '
                f'prefer outcome-oriented verbs like "Reviews", "Builds", "Calculates"',
            ))

    # No tags
    tags = payload.get("tags")
    if isinstance(tags, list) and len(tags) == 0:
        hints.append(_issue(
            "tags",
            "no tags set — add at least one for analytics filtering and discovery",
        ))

    # No conversational trigger phrases
    triggers = payload.get("triggers")
    if isinstance(triggers, list) and triggers:
        joined = " | ".join(
            t.lower() for t in triggers if isinstance(t, str)
        )
        if not any(cue in joined for cue in CONVERSATIONAL_CUES):
            hints.append(_issue(
                "triggers",
                'no conversational trigger phrases — consider adding variants '
                'like "can you help me with..." or "how do I..."',
            ))

    return hints


# ---------------------------------------------------------------------------
# Public interface — dict-based (Maestro-compat)
# ---------------------------------------------------------------------------

def validate_skill(payload: dict, is_update: bool = False) -> dict:
    """Validate a skill payload and return a tiered result.

    Returns:
        {
          "valid": bool,          # True iff errors is empty
          "errors": [ {field, message}, ... ],    # blocking
          "warnings": [ ... ],    # advisory (do not block save)
          "hints": [ ... ],       # quality suggestions
        }

    Never raises — always returns a dict.
    """
    errors = _check_errors(payload)
    warnings = _check_warnings(payload, is_update=is_update) if not errors else []
    hints = _check_hints(payload) if not errors else []
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "hints": hints,
    }


def validate_skill_payload(payload: dict) -> list[tuple[str, str]]:
    """Legacy single-tier validator (blocking errors only).

    Kept for backwards compatibility with existing call sites.
    New code should use validate_skill() directly.
    """
    result = validate_skill(payload)
    return [(e["field"], e["message"]) for e in result["errors"]]


# ---------------------------------------------------------------------------
# Public interface — Pydantic-based (external consumers)
# ---------------------------------------------------------------------------

def validate_skill_file(skill_file: SkillFile, is_update: bool = False) -> ValidationResult:
    """Validate a Pydantic SkillFile and return a ValidationResult dataclass.

    Thin wrapper over `validate_skill`. Preferred when working with the
    Pydantic `SkillFile` type directly rather than a dict payload. Flattens
    `{field, message}` dicts to human-readable strings — use the dict-based
    `validate_skill` if you need the field key separately.
    """
    payload = skill_file.model_dump(mode="python")
    # Flatten nested execution_hints into top-level dict keys that the
    # dict-based validator understands.
    hints = payload.pop("execution_hints", None) or {}
    for k in ("locks_session", "lock_release_signals", "cancel_phrases"):
        if k in hints:
            payload[k] = hints[k]
    # Dates come back as date objects from Pydantic — convert to ISO strings
    # so _parse_iso_date accepts them the same way it accepts user input.
    for k in ("created", "updated", "approved_at", "review_due"):
        v = payload.get(k)
        if v is not None and hasattr(v, "isoformat"):
            payload[k] = v.isoformat()

    result = validate_skill(payload, is_update=is_update)
    word_count = _word_count(skill_file.body) if skill_file.body else 0
    return ValidationResult(
        valid=result["valid"],
        errors=[f"{e['field']}: {e['message']}" for e in result["errors"]],
        warnings=[f"{w['field']}: {w['message']}" for w in result["warnings"]],
        hints=[f"{h['field']}: {h['message']}" for h in result["hints"]],
        word_count=word_count,
    )
