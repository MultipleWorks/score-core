"""Score CLI — `score <subcommand>` entry point.

Commands:
  validate             Validate a single skill file or a directory
  library-check        Full library validation (overlaps, stale, coverage)
  governance-init      Report skills missing governance fields
  verify-recording     Verify the hash chain of a Recording file
  migrate              Add safe defaults for missing spec fields

Exit codes:
  0  success
  1  validation errors (or chain verification failed)
  2  tool error (file not found, malformed YAML, etc)
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import click

from score.parser import parse_skill_file
from score.validator import validate_skill
from score.library_validator import validate_library, propose_fixes_for_report
from score.recording import verify_recording_file


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="score-core")
def cli():
    """Score — portable AI knowledge format CLI."""


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--strict", is_flag=True, help="Treat warnings as errors.")
def validate(path: Path, strict: bool):
    """Validate a single skill file or every .md file in a directory."""
    if path.is_dir():
        files = sorted(path.glob("**/*.md"))
        if not files:
            click.echo(f"No .md files found in {path}", err=True)
            sys.exit(2)
    else:
        files = [path]

    total_errors = 0
    total_warnings = 0
    total_files = 0
    failed_files = 0

    for file_path in files:
        total_files += 1
        skill = parse_skill_file(str(file_path))
        if skill is None:
            click.secho(f"✗ {file_path}: could not parse", fg="red")
            total_errors += 1
            failed_files += 1
            continue

        payload = _skill_to_payload(skill)
        result = validate_skill(payload)
        has_errors = len(result["errors"]) > 0
        has_warnings = len(result["warnings"]) > 0

        total_errors += len(result["errors"])
        total_warnings += len(result["warnings"])

        if has_errors or (strict and has_warnings):
            failed_files += 1
            colour = "red"
            mark = "✗"
        elif has_warnings:
            colour = "yellow"
            mark = "!"
        else:
            colour = "green"
            mark = "✓"

        click.secho(f"{mark} {file_path.name}", fg=colour)
        for e in result["errors"]:
            click.echo(f"    error: {e['field']} — {e['message']}")
        for w in result["warnings"]:
            click.echo(f"    warning: {w['field']} — {w['message']}")
        if strict and has_warnings and not has_errors:
            click.echo("    (strict mode — warnings treated as errors)")

    click.echo()
    click.echo(
        f"{total_files} file(s) checked — "
        f"{total_errors} error(s), {total_warnings} warning(s)"
    )

    if failed_files > 0:
        sys.exit(1)


# ---------------------------------------------------------------------------
# library-check
# ---------------------------------------------------------------------------

@cli.command(name="library-check")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
def library_check(directory: Path):
    """Run full library validation (overlaps, coverage, governance)."""
    skills = _load_skills_from_directory(directory)
    if not skills:
        click.echo(f"No valid skill files in {directory}", err=True)
        sys.exit(2)

    report = validate_library(skills)
    summary = report["summary"]

    click.echo(f"Library: {directory}")
    click.echo(f"  Skills: {summary['total_skills']} "
               f"({summary['active_skills']} active)")
    click.echo(f"  Overall health: {summary['overall_health']}")
    click.echo()
    click.echo(f"  Skills with errors:   {summary['skills_with_errors']}")
    click.echo(f"  Skills with warnings: {summary['skills_with_warnings']}")
    click.echo(f"  Skills with hints:    {summary['skills_with_hints']}")
    click.echo(f"  Trigger overlaps:     {summary['trigger_overlaps']}")

    findings = report["library_findings"]
    if findings["trigger_overlaps"]:
        click.echo()
        click.echo("Trigger overlaps:")
        for o in findings["trigger_overlaps"]:
            click.echo(f"  '{o['trigger']}' → {', '.join(o['skills'])}")

    if findings["tag_coverage"]["skills_with_no_tags"]:
        click.echo()
        click.echo("Skills with no tags:")
        for name in findings["tag_coverage"]["skills_with_no_tags"]:
            click.echo(f"  {name}")

    if summary["skills_with_errors"] > 0:
        sys.exit(1)


# ---------------------------------------------------------------------------
# governance-init
# ---------------------------------------------------------------------------

@cli.command(name="governance-init")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
def governance_init(directory: Path):
    """Report skills missing v0.1.1 governance fields + suggest defaults."""
    skills = _load_skills_from_directory(directory)
    if not skills:
        click.echo(f"No valid skill files in {directory}", err=True)
        sys.exit(2)

    governance_fields = ("approved_by", "approved_at", "review_due", "classification")
    needs_migration: list = []
    compliant: list = []

    for skill in skills:
        missing = [f for f in governance_fields if not skill.get(f)]
        if missing:
            needs_migration.append((skill["name"], missing))
        else:
            compliant.append(skill["name"])

    click.echo(f"Skills scanned: {len(skills)}")
    click.echo(f"  Compliant:           {len(compliant)}")
    click.echo(f"  Needs migration:     {len(needs_migration)}")

    if needs_migration:
        click.echo()
        click.echo("Skills missing governance fields:")
        for name, missing in needs_migration:
            click.echo(f"  {name}: {', '.join(missing)}")
        click.echo()
        click.echo("Run `score migrate <dir> --to 0.1.1 --apply` to add safe defaults.")


# ---------------------------------------------------------------------------
# verify-recording
# ---------------------------------------------------------------------------

@cli.command(name="verify-recording")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def verify_recording(path: Path):
    """Verify the hash chain integrity of a Recording NDJSON file."""
    ok, reason = verify_recording_file(str(path))
    if ok:
        click.secho(f"✓ {path.name}: chain intact", fg="green")
    else:
        click.secho(f"✗ {path.name}: chain broken", fg="red")
        click.echo(f"  {reason}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--to", "target_version", required=True,
              help="Target Score spec version (currently only 0.1.1).")
@click.option("--apply", "apply_changes", is_flag=True,
              help="Write changes to files. Without --apply, shows a dry-run.")
@click.option("--skip-approved", is_flag=True,
              help="Skip skills that already have approved_by AND approved_at set.")
def migrate(directory: Path, target_version: str, apply_changes: bool, skip_approved: bool):
    """Upgrade a skill library to a target Score spec version.

    v0.1.1 adds four optional governance fields:
      approved_by, approved_at, review_due, classification

    This command adds SAFE DEFAULTS for fields that can be defaulted
    (classification: internal, review_due: +12 months) and PLACEHOLDER
    COMMENTS for fields that require human judgment (approved_by,
    approved_at). It does not bump skill version numbers — that happens
    when a human approves the skill.
    """
    if target_version != "0.1.1":
        click.echo(f"Unsupported target version: {target_version}", err=True)
        click.echo("Supported: 0.1.1", err=True)
        sys.exit(2)

    files = sorted(directory.glob("**/*.md"))
    if not files:
        click.echo(f"No .md files found in {directory}", err=True)
        sys.exit(2)

    plan = []  # list of (file_path, skill, missing_fields)
    already_compliant = []

    for file_path in files:
        skill = parse_skill_file(str(file_path))
        if skill is None:
            continue
        governance = {
            "approved_by": skill.approved_by,
            "approved_at": skill.approved_at,
            "review_due": skill.review_due,
            "classification": skill.classification,
        }
        missing = [k for k, v in governance.items() if not v]

        if not missing:
            already_compliant.append(file_path.name)
            continue

        if skip_approved and skill.approved_by and skill.approved_at:
            already_compliant.append(file_path.name)
            continue

        plan.append((file_path, skill, missing))

    click.echo(f"Scanning {len(files)} skill files in {directory}...")
    click.echo()
    click.echo(f"Skills requiring migration: {len(plan)}")
    click.echo(f"Skills already compliant:   {len(already_compliant)}")
    click.echo()

    if not plan:
        click.echo("Nothing to do.")
        return

    click.echo("Changes to be made:")
    for file_path, _skill, missing in plan:
        click.echo(f"  {file_path.name}  add: {', '.join(missing)}")

    default_review_due = (date.today() + timedelta(days=365)).isoformat()

    click.echo()
    click.echo("Automatic defaults:")
    click.echo("  classification: internal (for skills missing this field)")
    click.echo(f"  review_due:     {default_review_due} (12 months from today)")
    click.echo()
    click.echo("Human completion required after migration:")
    click.echo("  approved_by, approved_at (cannot be safely defaulted)")

    if not apply_changes:
        click.echo()
        click.echo("Run with --apply to write changes.")
        return

    # Apply the migration
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.preserve_quotes = True

    applied: list = []
    failed: list = []

    for file_path, _skill, missing in plan:
        try:
            _apply_migration(file_path, missing, default_review_due, yaml)
            applied.append(file_path.name)
        except Exception as e:
            failed.append((file_path.name, str(e)))

    click.echo()
    click.secho(f"Migrated {len(applied)} skill files to Score v0.1.1.", fg="green")
    if failed:
        click.secho(f"Failed: {len(failed)}", fg="red")
        for name, err in failed:
            click.echo(f"  {name}: {err}")

    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Open each migrated skill and set approved_by + approved_at.")
    click.echo(f"  2. Run: score validate {directory} --strict")


def _apply_migration(
    file_path: Path,
    missing: list,
    default_review_due: str,
    yaml,
) -> None:
    """Apply governance-field migration to a single .md file.

    Uses ruamel.yaml for the frontmatter so comments, key order, and
    quoting are preserved. Field insertion order follows the canonical
    v0.1.1 schema: approved_by, approved_at, review_due, classification
    after `updated`.
    """
    # Read the file as text to split frontmatter from body manually —
    # python-frontmatter's round-trip doesn't preserve comments, and we
    # want ruamel.yaml to own the frontmatter block.
    text = file_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("file does not start with a YAML frontmatter fence")

    _, rest = text.split("---\n", 1)
    fm_text, body = rest.split("\n---\n", 1) if "\n---\n" in rest else (rest, "")
    # python-frontmatter writes `---\n<yaml>---\n<body>`. We split on
    # `\n---\n` which requires the closing fence to be on its own line.

    from io import StringIO
    data = yaml.load(StringIO(fm_text))

    # Insert the missing fields after `updated` in canonical order.
    order = ["approved_by", "approved_at", "review_due", "classification"]
    new_values = {}
    if "approved_by" in missing:
        new_values["approved_by"] = None
    if "approved_at" in missing:
        new_values["approved_at"] = None
    if "review_due" in missing:
        new_values["review_due"] = default_review_due
    if "classification" in missing:
        new_values["classification"] = "internal"

    # Find the position of `updated` and insert after it.
    keys = list(data.keys())
    if "updated" in keys:
        insert_after = keys.index("updated") + 1
    else:
        insert_after = len(keys)

    # ruamel.yaml CommentedMap supports insert(position, key, value)
    for i, field_name in enumerate(order):
        if field_name in new_values:
            data.insert(insert_after + i, field_name, new_values[field_name])

    # Re-serialise the frontmatter and write back.
    out = StringIO()
    yaml.dump(data, out)
    new_fm = out.getvalue()

    new_text = "---\n" + new_fm + "---\n" + body
    file_path.write_text(new_text, encoding="utf-8")

    # Verify the result still parses cleanly — if not, rewind.
    verify = parse_skill_file(str(file_path))
    if verify is None:
        raise ValueError("post-migration file does not parse cleanly")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill_to_payload(skill) -> dict:
    """Convert a Skill dataclass to the payload dict `validate_skill` expects."""
    return {
        "name": skill.name,
        "description": skill.description,
        "version": skill.version,
        "owner": skill.owner,
        "triggers": list(skill.triggers),
        "tags": list(skill.tags),
        "active": skill.active,
        "created": skill.created,
        "updated": skill.updated,
        "body": skill.body,
        "approved_by": skill.approved_by,
        "approved_at": skill.approved_at,
        "review_due": skill.review_due,
        "classification": skill.classification,
    }


def _load_skills_from_directory(directory: Path) -> list:
    """Load all .md files in a directory into validator payload dicts."""
    skills = []
    for file_path in sorted(directory.glob("**/*.md")):
        skill = parse_skill_file(str(file_path))
        if skill is None:
            continue
        skills.append(_skill_to_payload(skill))
    return skills


if __name__ == "__main__":
    cli()
