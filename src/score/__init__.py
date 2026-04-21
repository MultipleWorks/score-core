"""score — Core library for the Score portable AI knowledge format.

Public API re-exports. External consumers should import from `score`
directly rather than reaching into the submodules:

    from score import (
        # Schema
        SCORE_VERSION, APPROVED_TAGS, REFERENCE_TAGS,
        MIN_TRIGGERS, MAX_TRIGGERS, BODY_WARNING_WORDS, BODY_HINT_WORDS,
        Skill, SkillFile, UITheme, ExecutionHints, ValidationResult,

        # Parser / serialiser
        parse_skill_file, parse_skill_file_pydantic,
        serialise_skill_to_markdown, write_skill_file, default_file_path,

        # Validator
        validate_skill, validate_skill_file, validate_skill_payload,

        # Library validator
        validate_library, propose_fix, propose_fixes_for_report,

        # Context API models
        ContextRequest, ContextResponse, SkillForContext, OrgConfig,

        # Recording models
        RecordingEntry, compute_entry_hash, verify_recording_file,
    )
"""

__version__ = "0.1.2"

from score.schema import (
    ACCESS_CLASSIFICATIONS,
    APPROVED_TAGS,
    BODY_HINT_WORDS,
    BODY_SPARSE_WORDS,
    BODY_WARNING_WORDS,
    CLASSIFICATIONS,
    ExecutionHints,
    GOVERNANCE_FIELDS,
    MAX_TRIGGERS,
    MIN_TRIGGERS,
    REFERENCE_TAGS,
    REQUIRED_FRONTMATTER_FIELDS,
    SCORE_VERSION,
    Skill,
    SkillFile,
    UITheme,
    ValidationResult,
)
from score.parser import parse_skill_file, parse_skill_file_pydantic
from score.serialiser import (
    default_file_path,
    serialise_skill_to_markdown,
    serialize_skill_to_markdown,  # American-spelling alias
    write_skill_file,
)
from score.validator import (
    validate_classification_combination,
    validate_skill,
    validate_skill_file,
    validate_skill_payload,
)
from score.library_validator import (
    propose_fix,
    propose_fixes_for_report,
    validate_library,
)

__all__ = [
    # Version
    "__version__",
    "SCORE_VERSION",
    # Schema — constants
    "APPROVED_TAGS",
    "REFERENCE_TAGS",
    "MIN_TRIGGERS",
    "MAX_TRIGGERS",
    "BODY_WARNING_WORDS",
    "BODY_HINT_WORDS",
    "BODY_SPARSE_WORDS",
    "ACCESS_CLASSIFICATIONS",
    "CLASSIFICATIONS",
    "REQUIRED_FRONTMATTER_FIELDS",
    "GOVERNANCE_FIELDS",
    # Schema — types
    "Skill",
    "SkillFile",
    "UITheme",
    "ExecutionHints",
    "ValidationResult",
    # Parser
    "parse_skill_file",
    "parse_skill_file_pydantic",
    # Serialiser
    "serialise_skill_to_markdown",
    "serialize_skill_to_markdown",
    "write_skill_file",
    "default_file_path",
    # Validator
    "validate_classification_combination",
    "validate_skill",
    "validate_skill_file",
    "validate_skill_payload",
    # Library validator
    "validate_library",
    "propose_fix",
    "propose_fixes_for_report",
]
