"""Tests for the `score migrate` CLI command.

Covers:
  - 0.1.4 accepted as target (dry run, with no files)
  - 0.1.1 rejected with a clear error pointing at 0.1.4 and exit code 2
  - unrelated target version rejected with generic unsupported message
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from score.cli import cli


def test_migrate_to_0_1_1_is_rejected(tmp_path: Path):
    """Old CLI target must exit 2 with a message directing to 0.1.4."""
    (tmp_path / "placeholder.md").write_text("---\nname: x\n---\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["migrate", "--to", "0.1.1", str(tmp_path)])

    assert result.exit_code == 2
    # Error message mentions 0.1.4 so the user knows the correct target.
    assert "0.1.4" in result.output


def test_migrate_to_0_1_1_writes_no_changes(tmp_path: Path):
    """Rejecting the old target must not touch the directory."""
    skill = tmp_path / "skill.md"
    original = "---\nname: x\n---\n"
    skill.write_text(original)

    runner = CliRunner()
    runner.invoke(cli, ["migrate", "--to", "0.1.1", str(tmp_path)])

    assert skill.read_text() == original


def test_migrate_to_0_1_4_is_accepted(tmp_path: Path):
    """Current target must be accepted — even if no matching files present.

    We just care that the target-validation branch does not reject 0.1.4.
    Without --apply the command reports a plan and exits 0 (or 2 on empty
    dir, which is not the code path under test here — populate a file).
    """
    skill = tmp_path / "alpha-skill.md"
    skill.write_text(
        "---\nname: alpha-skill\n"
        "description: A test skill.\n"
        "version: 0.1.0\n"
        "owner: t@e.com\n"
        "triggers:\n- alpha trigger\n- run alpha\n"
        "tags:\n- operations\n"
        "active: true\ncreated: 2026-04-01\nupdated: 2026-04-05\n"
        "---\n\nBody.\n"
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["migrate", "--to", "0.1.4", str(tmp_path)])

    # Dry run — must not have rejected the target.
    assert "Unsupported target version" not in result.output
    assert "migration target '0.1.1' is not supported" not in result.output


def test_migrate_rejects_unrelated_target(tmp_path: Path):
    (tmp_path / "x.md").write_text("---\nname: x\n---\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["migrate", "--to", "0.2.9", str(tmp_path)])
    assert result.exit_code == 2
    assert "Unsupported target version" in result.output
