"""Score-format parser: markdown file → Skill.

Lenient by design — intended to be called by runtime skill loaders at
startup, where it should never crash on a malformed file. Returns `None`
and logs a warning if any required field is missing or malformed; the
caller is responsible for skipping the skill.

For strict authoring-time validation (errors / warnings / hints), use
`score.validator.validate_skill` against a payload dict.
"""

from __future__ import annotations

import logging
from typing import Optional

import frontmatter

from score.schema import REQUIRED_FRONTMATTER_FIELDS, Skill, SkillFile, UITheme

logger = logging.getLogger(__name__)


def parse_skill_file(file_path: str) -> Optional[Skill]:
    """Load a .md file and return a `Skill` dataclass. Returns None on defect.

    Defects logged at WARNING level: unreadable file, missing required
    frontmatter fields, empty/non-list triggers, non-boolean active,
    empty name. The function never raises.

    Returns a `Skill` dataclass (runtime-compatible) rather than a
    Pydantic `SkillFile` to match the existing Maestro runtime interface.
    For a Pydantic model, use `parse_skill_file_pydantic` instead.
    """
    parsed = _load_frontmatter(file_path)
    if parsed is None:
        return None
    metadata, body = parsed

    return Skill(
        score_version=str(metadata["score_version"]),
        name=metadata["name"],
        description=metadata["description"],
        version=str(metadata["version"]),
        owner=metadata["owner"],
        triggers=[str(t) for t in metadata["triggers"]],
        tags=[str(t) for t in metadata.get("tags", [])],
        active=metadata["active"],
        created=str(metadata["created"]),
        updated=str(metadata["updated"]),
        body=body,
        file_path=str(file_path),
        locks_session=bool(metadata.get("locks_session", False)),
        lock_release_signals=[str(s) for s in metadata.get("lock_release_signals", [])],
        cancel_phrases=[str(s) for s in metadata.get("cancel_phrases", [])],
        ui_theme=_parse_ui_theme(metadata.get("ui_theme")),
        approved_by=_optional_str(metadata.get("approved_by")),
        approved_at=_optional_str(metadata.get("approved_at")),
        review_due=_optional_str(metadata.get("review_due")),
        classification=_optional_str(metadata.get("classification")),
    )


def parse_skill_file_pydantic(file_path: str) -> Optional[SkillFile]:
    """Load a .md file and return a Pydantic SkillFile. Returns None on defect.

    Use this when working with score-core as an external library — the
    Pydantic model carries types (dates as `date`, classification as a
    Literal) that the runtime dataclass flattens to strings.
    """
    parsed = _load_frontmatter(file_path)
    if parsed is None:
        return None
    metadata, body = parsed

    try:
        return SkillFile(
            score_version=str(metadata["score_version"]),
            name=metadata["name"],
            description=metadata["description"],
            version=str(metadata["version"]),
            owner=metadata["owner"],
            triggers=[str(t) for t in metadata["triggers"]],
            tags=[str(t) for t in metadata.get("tags", [])],
            active=metadata["active"],
            created=metadata["created"],
            updated=metadata["updated"],
            body=body,
            approved_by=metadata.get("approved_by"),
            approved_at=metadata.get("approved_at"),
            review_due=metadata.get("review_due"),
            classification=metadata.get("classification"),
            execution_hints={
                "locks_session": bool(metadata.get("locks_session", False)),
                "lock_release_signals": [str(s) for s in metadata.get("lock_release_signals", [])],
                "cancel_phrases": [str(s) for s in metadata.get("cancel_phrases", [])],
                "ui_theme": _parse_ui_theme_dict(metadata.get("ui_theme")),
            },
            file_path=str(file_path),
        )
    except Exception as e:
        logger.warning("Skill %s failed Pydantic validation: %s", file_path, e)
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_frontmatter(file_path: str):
    """Shared loader for both parse_skill_file variants. Returns
    (metadata_dict, body_str) or None on any defect."""
    try:
        post = frontmatter.load(file_path)
    except Exception as e:
        logger.warning("Failed to parse frontmatter in %s: %s", file_path, e)
        return None

    metadata = post.metadata
    missing = REQUIRED_FRONTMATTER_FIELDS - set(metadata.keys())
    if missing:
        logger.warning("Skill %s missing required fields: %s", file_path, missing)
        return None

    if not isinstance(metadata.get("triggers"), list) or len(metadata["triggers"]) == 0:
        logger.warning("Skill %s has empty or invalid triggers", file_path)
        return None

    if not isinstance(metadata.get("active"), bool):
        logger.warning("Skill %s has non-boolean 'active' field", file_path)
        return None

    if not metadata.get("name"):
        logger.warning("Skill %s has empty name", file_path)
        return None

    return metadata, post.content


def _parse_ui_theme(raw):
    """Parse the optional ui_theme block into a UITheme Pydantic model.
    Returns None if absent or not a dict."""
    if not isinstance(raw, dict):
        return None
    return UITheme(
        brand_name=raw.get("brand_name"),
        primary_color=raw.get("primary_color"),
        accent_color=raw.get("accent_color"),
        logo_url=raw.get("logo_url"),
        heading_font=raw.get("heading_font"),
        body_font=raw.get("body_font"),
        tagline=raw.get("tagline"),
    )


def _parse_ui_theme_dict(raw):
    """Variant of _parse_ui_theme that returns a dict suitable for passing
    to the ExecutionHints Pydantic model (which expects Optional[UITheme]
    but accepts dicts via model validation)."""
    if not isinstance(raw, dict):
        return None
    return raw


def _optional_str(value):
    """Coerce a value to str if present, else return None.

    Used for governance fields — YAML may parse dates as date objects, and
    we want them as ISO strings on the runtime Skill dataclass for uniformity
    with `created` and `updated`.
    """
    if value is None:
        return None
    return str(value)
