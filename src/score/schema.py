"""Score format schema — Pydantic models and field constants.

This module is the single source of truth for the Score format data shape.
It defines:
  - Pydantic models (SkillFile, ExecutionHints, UITheme) used by external
    consumers and the Context API
  - Field constants (MIN_TRIGGERS, MAX_TRIGGERS, APPROVED_TAGS, etc.) used
    by the validator
  - The `Skill` dataclass, preserved for backwards compatibility with
    existing callers that expect the Maestro runtime dataclass interface

Field rules and authoring guidance live in `score.validator`.
Parsing lives in `score.parser`. Serialisation in `score.serialiser`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Format version
# ---------------------------------------------------------------------------

SCORE_VERSION = "0.1"
# Spec document revision this release of score-core targets. Distinct from
# SCORE_VERSION — SCORE_VERSION is the protocol version that appears in
# skill files (`score_version: "0.1"`). SPEC_REVISION tracks the authoring
# changelog of the specification document.
SPEC_REVISION = "0.1.4"


# ---------------------------------------------------------------------------
# Tag vocabulary
# ---------------------------------------------------------------------------

APPROVED_TAGS = {
    "brand", "proposals", "client-delivery", "pricing", "operations",
    "communications", "strategy", "research", "coaching", "maestro",
}

# Tags that identify "reference skills" — skills whose job is to expose
# factual information (brand assets, rate card, credentials). These benefit
# from a wider trigger surface area; the validator warns if reference skills
# have fewer than 4 triggers.
REFERENCE_TAGS = {"brand", "pricing"}


# ---------------------------------------------------------------------------
# Field thresholds (consumed by both validator and external UIs)
# ---------------------------------------------------------------------------

MIN_TRIGGERS = 2
MAX_TRIGGERS = 10

BODY_WARNING_WORDS = 400  # warn — approaching the 500-word limit
BODY_HINT_WORDS = 300     # hint — consider structure if unstructured
BODY_SPARSE_WORDS = 100   # hint — may be too sparse to be useful


# ---------------------------------------------------------------------------
# Required frontmatter fields (used by the lenient parser at load time)
# ---------------------------------------------------------------------------

REQUIRED_FRONTMATTER_FIELDS = frozenset({
    "score_version", "name", "description", "version", "owner",
    "triggers", "active", "created", "updated",
})

# Governance metadata fields introduced in Score v0.1.1. Optional on load —
# absent fields produce warnings, not errors. Will be required in v0.2.
GOVERNANCE_FIELDS = frozenset({
    "approved_by", "approved_at", "review_due", "classification",
})

CLASSIFICATIONS = frozenset({"public", "internal", "confidential", "secret"})
ACCESS_CLASSIFICATIONS = frozenset({"unrestricted", "restricted", "classified"})


# ---------------------------------------------------------------------------
# Pydantic models — canonical data types for external consumers
# ---------------------------------------------------------------------------

class UITheme(BaseModel):
    """Optional structured UI theming values carried by brand skills.

    All fields are optional — None means "use the host default". A loader
    that does not implement UI theming should ignore this entirely.
    """
    brand_name: Optional[str] = None
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None
    heading_font: Optional[str] = None
    body_font: Optional[str] = None
    tagline: Optional[str] = None


class ExecutionHints(BaseModel):
    """Optional execution-hint fields. Loaders that do not implement these
    must ignore them silently — they are not required for Score compatibility.
    """
    locks_session: bool = False
    lock_release_signals: list[str] = Field(default_factory=list)
    cancel_phrases: list[str] = Field(default_factory=list)
    ui_theme: Optional[UITheme] = None


class SkillFile(BaseModel):
    """A Score-format skill. Canonical Pydantic model for external consumers.

    Used by the Context API response and by anyone building a Score-compatible
    tool. The runtime dataclass `Skill` (below) is kept for backwards
    compatibility with the Maestro runtime — new code should prefer SkillFile.
    """
    score_version: str
    name: str
    description: str
    version: str
    owner: str
    triggers: list[str]
    tags: list[str] = Field(default_factory=list)
    active: bool
    created: date
    updated: date
    body: str = ""

    # v0.1.1 governance metadata — optional on load, warned if absent.
    approved_by: Optional[str] = None
    approved_at: Optional[date] = None
    review_due: Optional[date] = None
    classification: Optional[Literal["public", "internal", "confidential"]] = None

    # Execution hints — optional
    execution_hints: ExecutionHints = Field(default_factory=ExecutionHints)

    # Populated by the parser — not part of frontmatter
    file_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Runtime dataclass (backwards compatibility with Maestro)
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """A loaded Score-format skill, ready for routing and matching.

    Kept as a dataclass (not a Pydantic model) for backwards compatibility
    with the Maestro runtime, which passes Skill instances around hot paths
    where Pydantic validation overhead would matter. Mirror of SkillFile
    with flat field layout.

    New code should prefer SkillFile. This dataclass is retained so the
    Maestro runtime's skill loader, router, and context builder keep working
    without signature changes.
    """
    score_version: str
    name: str
    description: str
    version: str
    owner: str
    triggers: list
    tags: list
    active: bool
    created: str
    updated: str
    body: str
    file_path: str
    # Optional execution hints (not part of v0.1 required schema)
    locks_session: bool = False
    lock_release_signals: list = field(default_factory=list)
    cancel_phrases: list = field(default_factory=list)
    ui_theme: Optional[UITheme] = None
    # v0.1.1 governance metadata
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    review_due: Optional[str] = None
    classification: Optional[str] = None


# ---------------------------------------------------------------------------
# Validation result shape (shared between CLI and library validator)
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Structured outcome of validating a single skill file.

    The Maestro runtime uses the dict-based `validate_skill(payload, is_update)`
    interface for historical compatibility. External consumers working with
    Pydantic `SkillFile` objects prefer this dataclass — returned by
    `validate_skill_file(skill_file)`.
    """
    valid: bool
    errors: list[str]
    warnings: list[str]
    hints: list[str]
    word_count: int
