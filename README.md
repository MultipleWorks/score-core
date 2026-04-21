# score-core

Core library for the Score portable AI knowledge format.

Score is a human-readable, LLM-agnostic format for encoding organisational
knowledge as portable skill files. `score-core` provides the schema, parser,
serialiser, validator, library validator, Context API models, and Recording
models that any Score-compatible tool needs.

Full format specification: [score_spec.md](https://github.com/multipleworks/score/blob/main/score_spec.md)
Writing skills: [WRITING_SKILLS.md](https://github.com/multipleworks/score/blob/main/WRITING_SKILLS.md)

## Install

```bash
pip install score-core
```

## Quickstart

### Validate a skill file

```bash
score validate path/to/my-skill.md
score validate path/to/skills/ --strict
```

### Validate programmatically

```python
from score import parse_skill_file, validate_skill

skill = parse_skill_file("path/to/my-skill.md")
payload = {
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
}

result = validate_skill(payload)
if not result["valid"]:
    for error in result["errors"]:
        print(f"error: {error['field']} — {error['message']}")
for warning in result["warnings"]:
    print(f"warning: {warning['field']} — {warning['message']}")
```

### Work with the Pydantic model

```python
from score import parse_skill_file_pydantic, validate_skill_file

skill_file = parse_skill_file_pydantic("path/to/my-skill.md")
result = validate_skill_file(skill_file)
print(result)  # ValidationResult(valid=True, errors=[], warnings=[...], ...)
```

### Library validation

```python
from score import validate_library

skills = [...]  # list of full skill dicts
report = validate_library(skills)
print(report["summary"]["overall_health"])  # "good" | "warning" | "critical"
```

### Migrate existing skills to v0.1.1

```bash
score migrate path/to/skills/ --to 0.1.1           # dry run
score migrate path/to/skills/ --to 0.1.1 --apply   # write changes
```

## CLI commands

| Command | Purpose |
|---------|---------|
| `score validate <path>` | Validate a single file or directory |
| `score library-check <dir>` | Full library report (overlaps, coverage) |
| `score governance-init <dir>` | Report skills missing v0.1.1 governance fields |
| `score verify-recording <file>` | Verify Recording hash chain integrity |
| `score migrate <dir> --to 0.1.1` | Add safe defaults for new spec fields |

## What's in the package

- `score.schema` — Pydantic models (`SkillFile`, `UITheme`, `ExecutionHints`) and field constants
- `score.parser` — `.md` → `Skill` (runtime dataclass) and `SkillFile` (Pydantic)
- `score.serialiser` — `Skill` → `.md` with YAML frontmatter
- `score.validator` — three-tier validation (errors, warnings, hints)
- `score.library_validator` — cross-skill checks and fix proposal
- `score.context_api` — request/response models for the Score Context API
- `score.recording` — audit log entry models and hash chain utilities
- `score.cli` — `score` command-line interface

## Relationship to Maestro

Maestro is the commercial skill management product built on the Score format.
`score-core` is the shared library that Maestro and any other Score-compatible
tool import. Maestro uses `score-core` internally; it is not a Maestro
dependency.

## Version

Current: **0.1.0** — supports Score format v0.1.1 with governance metadata fields.

## Licence

MIT. See [LICENCE](LICENCE).
