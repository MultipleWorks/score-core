"""Score Context API — Pydantic request/response models.

These are the canonical data types for the Score Context API v0.1.0, as
specified in `docs/score_context_api_spec.md`. Implementations of the
API (e.g. Maestro's management layer) should use these models directly
for request parsing and response construction.

This module contains DATA TYPES ONLY. The FastAPI route implementation,
authentication, skill matching, rate limiting, and error response
construction live in the management layer, not here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from score.schema import ExecutionHints


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

Interface = Literal["telegram", "slack", "teams", "api", "web", "mcp"]


class CallerInfo(BaseModel):
    """Identifies the calling runtime and the interface the query arrived on.

    `runtime_version` is a semver string — the management layer logs it
    and may use it for compatibility checks.
    """
    runtime_version: str
    interface: Interface


class IdentityInfo(BaseModel):
    """User identity block — carries a verified token from the org's
    identity provider. The management layer validates this and resolves
    it to a role that determines which skills the user is permitted to
    receive.

    In single-user deployments, `token_type` is `"api_key"` and the
    management layer grants full access. Multi-user deployments must use
    `"jwt"` or `"saml"`.
    """
    token: str
    token_type: Literal["jwt", "saml", "api_key"]
    user_id: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    verified_by: Optional[str] = None


class RequestMetadata(BaseModel):
    """Per-request metadata — execution timestamp."""
    timestamp: datetime


PermissionTier = Literal["public", "internal", "confidential"]


class ContextRequest(BaseModel):
    """POST /v1/context request body.

    `query` is the raw user message. Maximum 4,000 characters — the
    management layer rejects longer queries with HTTP 422.

    `identity` is required for multi-user deployments. If absent or null,
    the management layer applies the most restrictive default (public-only
    skills). Single-user deployments may omit it.
    """
    query: str = Field(..., max_length=4000)
    session_id: Optional[str] = None
    caller: CallerInfo
    identity: Optional[IdentityInfo] = None
    metadata: RequestMetadata


# ---------------------------------------------------------------------------
# Response — skill and config sub-types
# ---------------------------------------------------------------------------

class SkillVersionRef(BaseModel):
    """Name + exact version of a skill that fired for a request.

    Used in the audit section of the response and in Recording entries.
    The version is immutable — once a skill is served at version X, the
    audit chain records X regardless of later updates.
    """
    name: str
    version: str


Classification = Literal["public", "internal", "confidential"]


class SkillForContext(BaseModel):
    """A skill as returned by the Context API.

    Structurally similar to `SkillFile` but with trimmed fields — the
    Context API response omits authoring metadata (created, updated,
    owner) that the runtime does not need for execution. The management
    layer carries those fields for internal governance.
    """
    name: str
    version: str
    description: str
    body: str
    tags: list[str] = Field(default_factory=list)
    owner: str
    execution_hints: ExecutionHints = Field(default_factory=ExecutionHints)
    # v0.1.1 governance fields — optional in the response. `classification`
    # governs LLM routing: 'confidential' skills force local model.
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    classification: Optional[Classification] = None


class HonestyProtocolConfig(BaseModel):
    """Per-org honesty protocol configuration.

    `enabled` should always be True in production — the runtime should
    warn if an org disables the honesty protocol. `org_signal_phrases`
    is the list of substrings that mark a query as organisational; the
    runtime uses this to decide whether a zero-match query should trigger
    the refusal or fall through to a general LLM.
    """
    enabled: bool = True
    org_signal_phrases: list[str] = Field(default_factory=list)
    refusal_message: str


class LLMRoutingConfig(BaseModel):
    """LLM routing policy for this org.

    `default` is applied when no skill classification forces a route.
    `confidential_override` is always 'local' and not configurable — a
    hard constraint from the spec: confidential skills never route to cloud.
    `local_model` / `cloud_model` are human-readable identifiers (e.g.
    "ollama/llama3", "claude-sonnet-4-6"); the runtime maps these to its
    own provider implementations.

    `sensitive_tier_enabled` and `sensitive_tier_endpoint` are Phase 3
    additions for two-tier deployments. In Phase 2, both are absent —
    the runtime treats their absence as sensitive_tier_enabled=False.
    """
    default: Literal["local", "cloud"]
    confidential_override: Literal["local"] = "local"
    sensitive_tier_enabled: bool = False
    sensitive_tier_endpoint: Optional[str] = None
    local_model: Optional[str] = None
    cloud_model: Optional[str] = None


class InterfaceConfig(BaseModel):
    """Whether a given interface (telegram, slack, teams, api, web) is
    enabled for this org. The runtime must refuse connections on disabled
    interfaces.
    """
    enabled: bool


class BrandingConfig(BaseModel):
    """Org branding for the runtime to present in its interfaces.

    `theme` is a free-form dict derived from the active brand skill's
    `ui_theme` block (or the org's config.yaml override). Not parsed
    by the Context API — passed through to the runtime verbatim.
    """
    assistant_name: str
    logo_url: Optional[str] = None
    theme: Optional[dict] = None


class OrgConfig(BaseModel):
    """The full org config block returned with every Context API response.

    Always present, regardless of whether skills matched. The runtime
    caches this for the session and refreshes it on each context call.
    """
    org_id: str
    org_name: str
    honesty_protocol: HonestyProtocolConfig
    llm_routing: LLMRoutingConfig
    interfaces: dict[str, InterfaceConfig]
    branding: BrandingConfig
    score_version: str


class AuditInfo(BaseModel):
    """Audit metadata attached to every Context API response.

    `query_hash` is SHA-256 of the raw query — the runtime can store
    this in its Recording without storing the query itself. `caller_key_id`
    is an opaque identifier for the API key that authenticated the call
    — never the key itself.

    v0.1.1 additions: `user_id`, `resolved_role`, `permission_tier` —
    records what identity was resolved and what permission level was
    applied. `permission_tier` is the highest classification the user
    was permitted to access for this request.
    """
    org_id: str
    caller_key_id: str
    user_id: Optional[str] = None
    resolved_role: Optional[str] = None
    permission_tier: PermissionTier = "public"
    query_hash: str
    skill_versions: list[SkillVersionRef] = Field(default_factory=list)
    timestamp: datetime


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ContextResponse(BaseModel):
    """POST /v1/context response body.

    `matched=false + gap_logged=true` means the honesty protocol should
    fire — the runtime returns `config.honesty_protocol.refusal_message`
    and does NOT call any LLM. This is HTTP 200, not an error.

    `matched=false + gap_logged=false` means no organisational signal was
    detected — the runtime falls through to the general LLM.
    """
    request_id: str
    matched: bool
    gap_logged: bool
    skills: list[SkillForContext] = Field(default_factory=list)
    config: OrgConfig
    audit: AuditInfo


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------

ErrorCode = Literal[
    "invalid_request",
    "unauthorised",
    "forbidden",
    "org_not_found",
    "query_too_long",
    "rate_limited",
    "internal_error",
    "unavailable",
]


class ErrorDetail(BaseModel):
    """Structured error detail included in the error response body."""
    code: ErrorCode
    message: str
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response envelope. Used for all non-200 responses except
    the honesty protocol firing (which is a 200 with matched=false)."""
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """GET /v1/health response. No auth required."""
    status: Literal["ok", "degraded", "error"] = "ok"
    version: str
    timestamp: datetime
