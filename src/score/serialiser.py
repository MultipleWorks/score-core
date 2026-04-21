"""Score-format serialiser: Skill → markdown text or .md file.

Mirror of `score.parser`. Emits frontmatter fields in canonical order,
omits optional fields when unset so simple skills stay simple on disk.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter

from score.schema import SCORE_VERSION, Skill


def _build_frontmatter(skill: Skill) -> dict:
    """Compose the frontmatter dict in canonical (human-readable) order.

    Field order:
      1. score_version, name, description, version, owner
      2. triggers, tags
      3. active, created, updated
      4. approved_by, approved_at, review_due, classification  (v0.1.1)
      5. locks_session, lock_release_signals, cancel_phrases    (execution hints)
      6. ui_theme                                               (execution hints)

    Optional fields are only included when they have non-default values.
    """
    fm = {
        "score_version": SCORE_VERSION,
        "name": skill.name,
        "description": skill.description,
        "version": skill.version,
        "owner": skill.owner,
        "triggers": list(skill.triggers),
        "tags": list(skill.tags),
        "active": skill.active,
        "created": skill.created,
        "updated": skill.updated,
    }

    # v0.1.1 governance metadata — include only when set
    if skill.approved_by is not None:
        fm["approved_by"] = skill.approved_by
    if skill.approved_at is not None:
        fm["approved_at"] = skill.approved_at
    if skill.review_due is not None:
        fm["review_due"] = skill.review_due
    if skill.classification is not None:
        fm["classification"] = skill.classification

    # Execution hints
    if skill.locks_session:
        fm["locks_session"] = True
        if skill.lock_release_signals:
            fm["lock_release_signals"] = list(skill.lock_release_signals)
        if skill.cancel_phrases:
            fm["cancel_phrases"] = list(skill.cancel_phrases)
    if skill.ui_theme is not None:
        theme_dict = {}
        for field in ("brand_name", "primary_color", "accent_color",
                      "logo_url", "heading_font", "body_font", "tagline"):
            val = getattr(skill.ui_theme, field, None)
            if val is not None:
                theme_dict[field] = val
        if theme_dict:
            fm["ui_theme"] = theme_dict
    return fm


def serialise_skill_to_markdown(skill: Skill) -> str:
    """Return the full markdown text (frontmatter + body) for a Skill.

    The output ends with a single trailing newline so files round-trip
    cleanly through git diff.
    """
    post = frontmatter.Post(skill.body, **_build_frontmatter(skill))
    return frontmatter.dumps(post) + "\n"


# American-spelling alias for backwards compatibility with Maestro callers
# that used the `serialize_skill_to_markdown` name. Both work.
serialize_skill_to_markdown = serialise_skill_to_markdown


def write_skill_file(skill: Skill, path: str) -> None:
    """Write a Skill to disk as a .md file with YAML frontmatter.

    Creates parent directories as needed. Overwrites any existing file.
    """
    md = serialise_skill_to_markdown(skill)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(md)


def default_file_path(name: str, skills_dir: str = "skills") -> str:
    """Compute the default on-disk location for a new skill.

    MW-prefixed skills (`mw-…`) live in `<skills_dir>/mw/`; everything else
    goes to `<skills_dir>/` directly. This reflects the Maestro convention —
    third parties using score-core with a flat skill library can pass any
    `skills_dir` and get `<skills_dir>/<name>.md` for non-MW skills.
    """
    if name.startswith("mw-"):
        return f"{skills_dir}/mw/{name}.md"
    return f"{skills_dir}/{name}.md"
