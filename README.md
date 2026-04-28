# score-core

Python reference implementation of the Score specification for AI skills.

Score is a vendor-independent specification format for AI skills - skill files describe what an AI system should know, what it is allowed to do, and what governance applies, in a format that compiles to runtime targets like Anthropic Skills, MCP server configurations, and OpenAI tools. `score-core` provides the schema, parser, serialiser, validator, library validator, Context API models, and Recording models that any Score-compatible tool needs.

Full format specification: [score_spec.md](https://github.com/multipleworks/score/blob/main/score_spec.md)
Writing skills: [WRITING_SKILLS.md](https://github.com/multipleworks/score/blob/main/WRITING_SKILLS.md)
Broader architecture: [multipleworks.com.hk/briefings](https://multipleworks.com.hk/briefings)

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
        print(f"error: {error['field']} - {error['message']}")
for warning in result["warnings"]:
    print(f"warning: {warning['field']} - {warning['message']}")
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

### Migrate existing skills to the latest spec revision

```bash
score migrate path/to/skills/ --to 0.1.4           # dry run
score migrate path/to/skills/ --to 0.1.4 --apply   # write changes
```

The `--to 0.1.4` target adds the governance metadata fields (`approved_by`, `approved_at`, `review_due`, `classification`) introduced in spec revision 0.1.4 with safe defaults.

## CLI commands

| Command | Purpose |
|---------|---------|
| `score validate <path>` | Validate a single file or directory |
| `score library-check <dir>` | Full library report (overlaps, coverage) |
| `score governance-init <dir>` | Report skills missing v0.1.4 governance fields |
| `score verify-recording <file>` | Verify Recording hash chain integrity |
| `score migrate <dir> --to 0.1.4` | Add safe defaults for new spec fields |

## What's in the package

- `score.schema` - Pydantic models (`SkillFile`, `UITheme`, `ExecutionHints`) and field constants
- `score.parser` - `.md` to `Skill` (runtime dataclass) and `SkillFile` (Pydantic)
- `score.serialiser` - `Skill` to `.md` with YAML frontmatter
- `score.validator` - three-tier validation (errors, warnings, hints)
- `score.library_validator` - cross-skill checks and fix proposal
- `score.context_api` - request/response models for the Score Context API
- `score.recording` - audit log entry models and hash chain utilities
- `score.cli` - `score` command-line interface

## Relationship to Score and Maestro

Score is the specification format. `score-core` is the Python reference implementation - the parser, validator, and supporting models that any Score-compatible tool can use.

Maestro is the commercial skill management product built on the Score format. Maestro uses `score-core` internally as a library; `score-core` itself has no dependency on Maestro and runs standalone.

## Version

Current: **0.1.4** - supports Score format spec revision 0.1.4 including governance metadata fields.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to score-core.

## Licence

MIT. See [LICENCE](LICENCE).
