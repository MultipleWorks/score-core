"""Library-wide validation and fix proposal — pure functions.

Runs `validate_skill` across a list of skills, adds cross-skill checks
that per-skill validation cannot see (trigger overlaps, tag coverage),
and turns individual findings into concrete proposed changes.

This module has ZERO knowledge of databases, file systems, or other
runtime state. All data is passed in as dicts. Callers that need DB
access (like the Maestro API `/library/health` endpoint) fetch skills
themselves then call `validate_library(skills, stale_info=...)`.

Stale-skill detection requires a message log the caller owns, so
`validate_library` accepts an optional `stale_info` dict rather than
pulling from a DB itself. If stale_info is None, the stale findings
section is empty.
"""

from __future__ import annotations

import uuid
from typing import Optional

from score.schema import APPROVED_TAGS
from score.validator import VAGUE_VERBS, validate_skill


STALE_DAYS = 30


def validate_library(
    skills: list,
    include_inactive: bool = True,
    stale_info: Optional[dict] = None,
) -> dict:
    """Run full validation across a list of skills.

    Args:
        skills: List of full skill dicts — each must contain the fields
            validate_skill() expects. Callers are responsible for fetching
            these from wherever they live (DB, filesystem, etc).
        include_inactive: If False, inactive skills are filtered out before
            validation. Default True so the report covers the full library.
        stale_info: Optional dict keyed by skill name with values either:
            - None  (skill has never been triggered)
            - dict like {"last_triggered": ISO-str, "days_since_triggered": int}
            If omitted, the stale_skills section of the report is empty.

    Returns a LibraryReport dict.
    """
    if not include_inactive:
        skills = [s for s in skills if s.get("active")]

    per_skill: list = []
    for skill in skills:
        payload = _skill_to_validator_payload(skill)
        result = validate_skill(payload)
        per_skill.append({
            "name": skill["name"],
            "active": skill["active"],
            "valid": result["valid"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "hints": result["hints"],
        })

    active_skills = [s for s in skills if s.get("active")]
    trigger_overlaps = _detect_trigger_overlaps(active_skills)
    tag_coverage = _compute_tag_coverage(active_skills)
    stale_skills = _filter_stale_skills(active_skills, stale_info)

    skills_with_errors = sum(1 for s in per_skill if s["errors"])
    skills_with_warnings = sum(1 for s in per_skill if s["warnings"])
    skills_with_hints = sum(1 for s in per_skill if s["hints"])
    unintentional_overlaps = [o for o in trigger_overlaps if not o["intentional"]]

    overall_health = _compute_overall_health(
        skills_with_errors=skills_with_errors,
        skills_with_warnings=skills_with_warnings,
        unintentional_overlaps=len(unintentional_overlaps),
        stale_count=len(stale_skills),
    )

    return {
        "summary": {
            "total_skills": len(skills),
            "active_skills": sum(1 for s in skills if s.get("active")),
            "skills_with_errors": skills_with_errors,
            "skills_with_warnings": skills_with_warnings,
            "skills_with_hints": skills_with_hints,
            "trigger_overlaps": len(trigger_overlaps),
            "stale_skills": len(stale_skills),
            "overall_health": overall_health,
        },
        "per_skill": per_skill,
        "library_findings": {
            "trigger_overlaps": trigger_overlaps,
            "tag_coverage": tag_coverage,
            "stale_skills": stale_skills,
        },
    }


def _compute_overall_health(
    skills_with_errors: int,
    skills_with_warnings: int,
    unintentional_overlaps: int,
    stale_count: int,
) -> str:
    if skills_with_errors > 0 or unintentional_overlaps > 3:
        return "critical"
    if skills_with_warnings > 0 or unintentional_overlaps > 0 or stale_count > 0:
        return "warning"
    return "good"


def _skill_to_validator_payload(skill: dict) -> dict:
    return {
        "name": skill["name"],
        "description": skill["description"],
        "version": skill["version"],
        "owner": skill["owner"],
        "triggers": list(skill["triggers"]),
        "tags": list(skill["tags"]),
        "active": skill["active"],
        "created": skill["created"],
        "updated": skill["updated"],
        "body": skill.get("body", ""),
        "approved_by": skill.get("approved_by"),
        "approved_at": skill.get("approved_at"),
        "review_due": skill.get("review_due"),
        "classification": skill.get("classification"),
    }


def _detect_trigger_overlaps(active_skills: list) -> list:
    trigger_to_skills: dict = {}
    for skill in active_skills:
        for trigger in skill["triggers"]:
            key = trigger.lower().strip()
            if not key:
                continue
            trigger_to_skills.setdefault(key, []).append(skill["name"])

    overlaps: list = []
    for key, skill_names in trigger_to_skills.items():
        uniq = sorted(set(skill_names))
        if len(uniq) < 2:
            continue
        overlaps.append({
            "trigger": key,
            "skills": sorted(uniq),
            "intentional": False,
        })
    return sorted(overlaps, key=lambda o: o["trigger"])


def _compute_tag_coverage(active_skills: list) -> dict:
    used: set = set()
    skills_with_no_tags: list = []
    for skill in active_skills:
        if not skill["tags"]:
            skills_with_no_tags.append(skill["name"])
        for tag in skill["tags"]:
            if tag in APPROVED_TAGS:
                used.add(tag)
    return {
        "used_tags": sorted(used),
        "unused_tags": sorted(APPROVED_TAGS - used),
        "skills_with_no_tags": sorted(skills_with_no_tags),
    }


def _filter_stale_skills(
    active_skills: list,
    stale_info: Optional[dict],
) -> list:
    """Return the stale-skills report section.

    stale_info contract:
      - None: caller did not provide stale data — no stale section.
      - dict: keys are names of skills the caller considers stale.
        Values are None (never triggered) or {"last_triggered": str,
        "days_since_triggered": int|None}. Skills NOT in the dict are
        considered not-stale and are omitted from the report.
    """
    if stale_info is None:
        return []

    active_names = {s["name"] for s in active_skills}
    stale: list = []
    for name, info in stale_info.items():
        if name not in active_names:
            continue
        if info is None:
            stale.append({
                "name": name,
                "last_triggered": None,
                "days_since_triggered": None,
            })
        elif isinstance(info, dict):
            stale.append({
                "name": name,
                "last_triggered": info.get("last_triggered"),
                "days_since_triggered": info.get("days_since_triggered"),
            })
    return sorted(
        stale,
        key=lambda s: s["days_since_triggered"] if s["days_since_triggered"] is not None else 9999,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Fix proposals
# ---------------------------------------------------------------------------

FINDING_TYPES = ("error", "warning", "hint", "overlap", "stale")

ACTION_EDIT_FIELD = "edit_field"
ACTION_REMOVE_TRIGGER = "remove_trigger"
ACTION_DEACTIVATE = "deactivate"
ACTION_NO_FIX = "no_fix"


def propose_fixes_for_report(
    report: dict,
    skill_lookup: dict,
) -> list:
    """Generate ProposedChanges for every fixable finding in a report.

    Args:
        report: LibraryReport returned by validate_library()
        skill_lookup: dict mapping skill_name -> full skill dict. Must
            contain an entry for every skill referenced in the report.
    """
    proposals: list = []

    for skill_report in report["per_skill"]:
        full = skill_lookup.get(skill_report["name"])
        if full is None:
            continue
        for finding_type_name, findings in (
            ("error", skill_report["errors"]),
            ("warning", skill_report["warnings"]),
            ("hint", skill_report["hints"]),
        ):
            for f in findings:
                proposal = propose_fix({
                    "finding_type": finding_type_name,
                    "skill": full,
                    "field": f["field"],
                    "message": f["message"],
                })
                if proposal is not None:
                    proposals.append(proposal)

    for overlap in report["library_findings"]["trigger_overlaps"]:
        if overlap["intentional"]:
            continue
        skills_data = [skill_lookup.get(n) for n in overlap["skills"]]
        skills_data = [s for s in skills_data if s is not None]
        if len(skills_data) < 2:
            continue
        proposal = propose_fix({
            "finding_type": "overlap",
            "trigger": overlap["trigger"],
            "skills": skills_data,
        })
        if proposal is not None:
            proposals.append(proposal)

    for stale in report["library_findings"]["stale_skills"]:
        proposal = propose_fix({
            "finding_type": "stale",
            "skill_name": stale["name"],
            "days_since_triggered": stale["days_since_triggered"],
        })
        if proposal is not None:
            proposals.append(proposal)

    return proposals


def propose_fix(finding: dict) -> Optional[dict]:
    ftype = finding["finding_type"]
    if ftype in ("error", "warning", "hint"):
        return _propose_per_skill_fix(finding)
    if ftype == "overlap":
        return _propose_overlap_fix(finding)
    if ftype == "stale":
        return _propose_stale_fix(finding)
    return None


def _make_change(
    skill_name: str,
    field: str,
    finding_type: str,
    finding_message: str,
    action: str,
    current_value,
    proposed_value,
    human_readable: str,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "skill_name": skill_name,
        "field": field,
        "finding_type": finding_type,
        "finding": finding_message,
        "proposed_action": action,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "human_readable": human_readable,
        "approved": None,
    }


def _propose_per_skill_fix(finding: dict) -> Optional[dict]:
    skill = finding["skill"]
    field = finding["field"]
    message = finding["message"]
    ftype = finding["finding_type"]
    name = skill["name"]

    if field == "description" and "full stop" in message:
        current = skill["description"]
        proposed = current.rstrip() + "."
        return _make_change(
            name, "description", ftype, message,
            ACTION_EDIT_FIELD, current, proposed,
            "Add a full stop to the end of the description.",
        )

    if field == "description" and "vague verb" in message:
        return _make_change(
            name, "description", ftype, message,
            ACTION_NO_FIX,
            skill["description"], skill["description"],
            f"Rewrite the description to start with an outcome-oriented verb "
            f"instead of one of: {', '.join(sorted(VAGUE_VERBS))}.",
        )

    if field.startswith("tags[") and "invalid tag" in message:
        bad_tag = _extract_quoted_token(message)
        if bad_tag is None or bad_tag not in skill["tags"]:
            return None
        closest = _closest_approved_tag(bad_tag)
        new_tags = [closest if t == bad_tag else t for t in skill["tags"]]
        return _make_change(
            name, "tags", ftype, message,
            ACTION_EDIT_FIELD,
            list(skill["tags"]), new_tags,
            f"Replace invalid tag '{bad_tag}' with '{closest}'.",
        )

    if field == "body" and ("approaching" in message or "word" in message):
        return _make_change(
            name, "body", ftype, message,
            ACTION_NO_FIX,
            skill["body"], skill["body"],
            "Body is too long. Split into two focused skills, or edit "
            "by hand to remove filler. Requires human judgment.",
        )

    if field == "change_summary":
        return _make_change(
            name, "change_summary", ftype, message,
            ACTION_NO_FIX, None, None,
            "Add a change summary on the next save.",
        )

    if field == "updated" and "equals created" in message:
        from datetime import date as _d
        today = _d.today().isoformat()
        return _make_change(
            name, "updated", ftype, message,
            ACTION_EDIT_FIELD,
            skill["updated"], today,
            f"Bump updated date to today ({today}) to reflect recent edit.",
        )

    if field == "body" and "first-person" in message:
        return _make_change(
            name, "body", ftype, message,
            ACTION_NO_FIX,
            skill["body"], skill["body"],
            "Rewrite body in second-person imperative. Requires manual editing.",
        )

    if field == "tags" and "no tags" in message:
        return _make_change(
            name, "tags", ftype, message,
            ACTION_NO_FIX,
            list(skill["tags"]), list(skill["tags"]),
            "Add at least one tag from the approved vocabulary.",
        )

    if field == "triggers" and "conversational" in message:
        return _make_change(
            name, "triggers", ftype, message,
            ACTION_NO_FIX,
            list(skill["triggers"]), list(skill["triggers"]),
            "Add conversational trigger variants (can you…, how do I…).",
        )

    if field == "triggers" and "reference skill" in message:
        return _make_change(
            name, "triggers", ftype, message,
            ACTION_NO_FIX,
            list(skill["triggers"]), list(skill["triggers"]),
            "Add more trigger variants — reference skills (brand, pricing) "
            "benefit from 8+ phrases for coverage.",
        )

    if field == "name":
        return _make_change(
            name, "name", ftype, message,
            ACTION_NO_FIX,
            skill["name"], skill["name"],
            "Skill name cannot be edited after creation. Deactivate and "
            "create a replacement with a kebab-case name.",
        )

    if field == "version" and "semver" in message:
        return _make_change(
            name, "version", ftype, message,
            ACTION_EDIT_FIELD,
            skill["version"], "0.1.0",
            "Set version to a valid semver string (0.1.0).",
        )

    if field == "body" and "structuring" in message:
        return _make_change(
            name, "body", ftype, message,
            ACTION_NO_FIX,
            skill["body"], skill["body"],
            "Add markdown headers/bullets to structure the body. Manual.",
        )

    return _make_change(
        name, field, ftype, message,
        ACTION_NO_FIX, None, None,
        f"Review this {ftype} manually — no automatic fix available.",
    )


def _propose_overlap_fix(finding: dict) -> Optional[dict]:
    trigger = finding["trigger"]
    skills = finding["skills"]
    if len(skills) < 2:
        return None

    scored = sorted(
        skills,
        key=lambda s: (
            -_trigger_name_affinity(trigger, s["name"]),
            len(s["triggers"]),
        ),
    )
    most_specific = scored[0]
    least_specific_candidates = scored[1:]

    top_key = (
        _trigger_name_affinity(trigger, most_specific["name"]),
        -len(most_specific["triggers"]),
    )
    tied = [
        s for s in scored
        if (_trigger_name_affinity(trigger, s["name"]), -len(s["triggers"])) == top_key
    ]
    if len(tied) > 1:
        return _make_change(
            skill_name=scored[0]["name"],
            field="triggers",
            finding_type="overlap",
            finding_message=(
                f"trigger '{trigger}' is shared by: "
                + ", ".join(s["name"] for s in scored)
            ),
            action=ACTION_NO_FIX,
            current_value=None,
            proposed_value=None,
            human_readable=(
                f"Multiple skills share the trigger '{trigger}'. Decide by "
                f"hand which skill should keep it; remove from the others."
            ),
        )

    least = least_specific_candidates[0]
    new_triggers = [t for t in least["triggers"] if t.lower().strip() != trigger.lower().strip()]
    return _make_change(
        skill_name=least["name"],
        field="triggers",
        finding_type="overlap",
        finding_message=(
            f"trigger '{trigger}' is also used by {most_specific['name']}"
        ),
        action=ACTION_REMOVE_TRIGGER,
        current_value=list(least["triggers"]),
        proposed_value=new_triggers,
        human_readable=(
            f"Remove '{trigger}' from {least['name']} — "
            f"{most_specific['name']} is more specific to this phrase."
        ),
    )


def _propose_stale_fix(finding: dict) -> dict:
    days = finding.get("days_since_triggered")
    reason = (
        f"not triggered in {days} days" if days is not None
        else "never triggered since import"
    )
    return _make_change(
        skill_name=finding["skill_name"],
        field="active",
        finding_type="stale",
        finding_message=reason,
        action=ACTION_DEACTIVATE,
        current_value=True,
        proposed_value=False,
        human_readable=f"Deactivate {finding['skill_name']} — {reason}.",
    )


def _extract_quoted_token(message: str) -> Optional[str]:
    start = message.find("'")
    if start == -1:
        return None
    end = message.find("'", start + 1)
    if end == -1:
        return None
    return message[start + 1:end]


def _closest_approved_tag(bad_tag: str) -> str:
    lower = bad_tag.lower()
    approved = sorted(APPROVED_TAGS)
    for tag in approved:
        if lower == tag:
            return tag
    for tag in approved:
        if lower.startswith(tag) or tag.startswith(lower):
            return tag
    for tag in approved:
        if lower in tag or tag in lower:
            return tag
    return "operations"


def _trigger_name_affinity(trigger: str, name: str) -> int:
    stopwords = {"a", "an", "the", "our", "my", "for", "of", "to", "and", "or"}
    trigger_words = {
        w.lower() for w in trigger.split() if w.lower() not in stopwords
    }
    name_words = {w.lower() for w in name.split("-")}
    return len(trigger_words & name_words)
