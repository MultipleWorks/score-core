# Score Context API
## Specification v0.1.1

**Status:** Draft
**Author:** Mark Goodchild, MultipleWorks
**Repository:** github.com/multipleworks/score
**Last updated:** April 2026

---

## Contents

- [Overview](#overview)
- [Design principles](#design-principles)
- [Permission architecture](#permission-architecture)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [POST /v1/context](#post-v1context)
  - [GET /v1/health](#get-v1health)
- [Request schema](#request-schema)
- [Response schema](#response-schema)
- [Skill object](#skill-object)
- [Config object](#config-object)
- [Error responses](#error-responses)
- [Versioning behaviour](#versioning-behaviour)
- [Implementing a Score-compatible runtime](#implementing-a-score-compatible-runtime)
- [Changelog](#changelog)

---

## Overview

The Score Context API is the standard interface between a Score runtime and a Score management layer (such as Maestro). It has one primary job: given a query from a user, return the set of approved, active skills that should govern the response, along with the organisation's configuration.

A runtime calls this API at query time. It does not cache skills locally, it does not maintain a local copy of the skill library, and it does not perform trigger matching itself. The management layer owns all of that logic. The runtime's job is to call the API, receive governed context, and use it.

The separation is intentional. It means:

- The governance layer has complete, real-time control over what the runtime knows.
- A skill that is revoked or updated takes effect immediately – the runtime picks up the change at its next context request.
- The runtime can be open-sourced and self-hosted without exposing the skill library.
- Third-party runtimes can be built against this spec and will behave consistently.

---

## Design principles

**The governance layer owns matching.** Trigger matching logic lives in the management layer, not the runtime. This prevents a runtime from bypassing governance by implementing its own matching strategy.

**The runtime requests context, not skills.** The API call carries a user query, not a list of skill names. The governance layer decides which skills are relevant. The runtime receives what it is given.

**Live version only.** The runtime cannot request a specific version of a skill. The governance layer determines what is live. The version is included in the response for audit purposes – not for selection by the caller.

**Config travels with context.** Organisation configuration is returned in the same call as skills. One round trip on startup and at query time. No separate config endpoint.

**Forward-compatible auth.** The current auth model uses API keys. The structure is designed to accommodate JWT and OAuth 2.0 in a future version without a breaking change to the request or response schema.

**Honest on gaps.** If no skills match a query that contains an organisational signal, the API returns an empty skills array with a `gap_logged` flag rather than returning a best-guess partial match. The runtime must honour this – it does not fall through to a general LLM response for organisational queries when no skills fire.

**The management layer is the trust boundary.** The context API enforces access control, not the runtime and not the LLM. The runtime passes the user's identity and role claim; the management layer verifies it against the organisation's identity provider and returns only the skills that role is permitted to receive. The LLM sees only what the user is authorised to see – not because it has been instructed to withhold, but because unauthorised content was never included in the response.

---

## Permission architecture

### Role-based context partitioning

When a request includes an `identity` block, the management layer uses the `role` and `department` fields to scope the skills returned. A user with the `general-staff` role receives only public and internal skills within their department scope. A user with the `senior-leadership` role receives the full approved library. A user with a specialist role (e.g. `finance-team`) receives confidential skills scoped to their domain.

The management layer resolves role-to-skill mappings at request time. Roles are defined in the management layer and map to combinations of classification levels and department tags. The runtime does not implement this logic – it passes the identity claim and trusts the response.

**Role resolution trust chain:**

1. The user authenticates with the organisation's identity provider (Azure AD, Okta, or equivalent).
2. The identity provider issues a verified role claim.
3. The runtime includes the role claim in the `identity` block of the context request.
4. The management layer verifies the claim against a trusted provider list (`identity.verified_by`).
5. The management layer resolves the role to a permission set and filters the skill library accordingly.
6. Only permitted skills are returned. The response contains no indication of what was withheld.

**Unauthenticated requests:** If the `identity` block is absent or null, the management layer applies the most restrictive default – public-only skills. Single-user deployments where IDAM is not configured operate in this mode by default.

**Untrusted role claims:** If `identity.verified_by` references an unknown or untrusted provider, the management layer rejects the role claim and falls back to the unauthenticated default. It does not return an error – doing so would reveal information about the permission system to a potential attacker.

### Two-tier LLM routing

Classification-based routing (confidential skills route to local model) remains in place. In a two-tier deployment, the second tier – a separate LLM instance on isolated infrastructure – handles confidential-classification queries for users with explicit sensitive-tier access. The `llm_routing` config object in the response indicates which tier should handle the query:

```json
"llm_routing": {
  "default": "local",
  "confidential_override": "local",
  "sensitive_tier_enabled": true,
  "sensitive_tier_endpoint": "http://sensitive-llm.internal:11434",
  "local_model": "ollama/llama3",
  "cloud_model": null
}
```

The `sensitive_tier_enabled` and `sensitive_tier_endpoint` fields are additions to the config object for Phase 3 deployments. In Phase 2, both are absent – the runtime treats their absence as `sensitive_tier_enabled: false` and routes per the existing classification logic.

---

## Authentication

### Current: API key

All requests must include an `Authorization` header:

```
Authorization: Bearer <api_key>
```

API keys are issued per organisation and per runtime instance. A key identifies both the organisation (determining which skill library is queried) and the caller (logged against every context request for audit purposes).

Keys are opaque strings. They carry no embedded claims. The management layer resolves the key to an organisation and a set of permissions at request time.

**Key scope:** In v0.1, a key grants access to the full approved skill library for an organisation. Scoped keys – granting access to a subset of skills by tag, department, or classification – are planned for v0.2.

**Key rotation:** Keys can be rotated without downtime. The management layer accepts both the old and new key for a configurable overlap period (default: 24 hours).

### Future: JWT / OAuth 2.0

In v0.2, the API will additionally accept a signed JWT in the `Authorization` header:

```
Authorization: Bearer <jwt>
```

The JWT will carry:

```json
{
  "iss": "https://auth.your-maestro-instance.com",
  "sub": "runtime-instance-id",
  "org": "org-id",
  "scope": ["context:read"],
  "exp": 1234567890
}
```

The transition will be non-breaking. API key auth will remain supported. Runtimes implementing against this spec should treat the `Authorization` header as opaque – do not parse it, simply include it as issued.

---

## Endpoints

### POST /v1/context

The primary endpoint. Returns matched skills and organisation config for a given query.

```
POST /v1/context
Authorization: Bearer <api_key>
Content-Type: application/json
```

### GET /v1/health

Returns the health status of the context API. No authentication required. Used by runtimes to verify connectivity on startup.

```
GET /v1/health
```

**Response:**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2026-04-16T09:00:00Z"
}
```

---

## Request schema

```json
{
  "query": "string",
  "session_id": "string | null",
  "caller": {
    "runtime_version": "string",
    "interface": "string"
  },
  "identity": {
    "token": "string",
    "token_type": "string",
    "user_id": "string | null",
    "role": "string | null",
    "department": "string | null",
    "verified_by": "string | null"
  },
  "metadata": {
    "timestamp": "string (ISO 8601)"
  }
}
```

### Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `query` | Yes | string | The raw user query. Used for trigger matching. Maximum 4,000 characters. |
| `session_id` | No | string or null | An opaque identifier for the current conversation session. Included in the audit log. If null, the request is treated as a single-turn query. |
| `caller.runtime_version` | Yes | string | Semver string identifying the runtime version. Used for compatibility checks and logged for audit. |
| `caller.interface` | Yes | string | The interface through which the query arrived. One of: `telegram`, `slack`, `teams`, `api`, `web`. Used for audit and for interface-specific config. |
| `identity.token` | Yes (multi-user) | string | A verified identity token from the organisation's identity provider – a JWT from an OAuth 2.0 or SAML flow. The management layer validates this token and resolves it to a role. In single-user deployments, this field may carry the org-level API key and the management layer treats the user as having full access. Required for all multi-user deployments. |
| `identity.token_type` | Yes (multi-user) | string | The type of token. One of: `jwt`, `saml`, `api_key`. Tells the management layer how to validate the token. |
| `identity.user_id` | No | string or null | An opaque identifier for the end user, as known to the calling system. Used as a fallback correlation key when the token cannot be resolved to a user. Never a name or email address. Logged for audit. |
| `identity.role` | No | string or null | The user's verified role identifier, as resolved by the organisation's identity provider. The management layer uses this to determine which skills the user is permitted to receive. Null in single-user deployments or where role-based access control is not yet configured. |
| `identity.department` | No | string or null | The user's department identifier. Used alongside `role` to scope department-specific skills. Null if not applicable. |
| `identity.verified_by` | No | string or null | Identifier of the identity provider that verified this role claim. The management layer should reject role claims from unknown or untrusted providers. Null if identity is not verified externally. |
| `metadata.timestamp` | Yes | string | ISO 8601 timestamp of when the query was received by the runtime, before the context API call. Used to establish the precise moment of execution in the audit log. |

### Identity resolution

The management layer resolves the `identity.token` to a permission role using the following sequence:

1. Validate the token against the organisation's configured identity provider.
2. Extract the user's role claim from the validated token.
3. Map the role to a set of permitted skill classifications and departments using the governance layer's access control rules.
4. Return only skills within the permitted set.

If the token is invalid or cannot be resolved to a role, the management layer returns `403 forbidden`. It does not fall back to a default role or return a partial skill set. An unresolvable identity is an access denial, not a degraded response.

In single-user deployments where `identity.token_type` is `api_key`, the management layer grants access to the full approved skill library for the organisation. This is the current Maestro deployment model. Multi-user deployments must use `jwt` or `saml` token types.

### Example request

```json
{
  "query": "Can you review this proposal before I send it to the client?",
  "session_id": "sess_a3f9b2c1",
  "caller": {
    "runtime_version": "0.2.1",
    "interface": "telegram"
  },
  "identity": {
    "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "jwt",
    "user_id": "usr_4821"
  },
  "metadata": {
    "timestamp": "2026-04-16T09:14:32Z"
  }
}
```

---

## Response schema

```json
{
  "request_id": "string",
  "matched": true | false,
  "gap_logged": true | false,
  "skills": [ <skill object>, ... ],
  "config": { <config object> },
  "audit": {
    "org_id": "string",
    "caller_key_id": "string",
    "user_id": "string | null",
    "resolved_role": "string | null",
    "permission_tier": "public | internal | confidential",
    "query_hash": "string",
    "skill_versions": [
      {
        "name": "string",
        "version": "string"
      }
    ],
    "timestamp": "string (ISO 8601)"
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | A unique identifier for this context request. Included in The Recording. The runtime should log this alongside the query and response. |
| `matched` | boolean | `true` if one or more skills fired. `false` if no skills fired. |
| `gap_logged` | boolean | `true` if the query contained an organisational signal but no skills matched. The management layer has logged this to the gap log. The runtime must honour the honesty protocol – see [Implementing a Score-compatible runtime](#implementing-a-score-compatible-runtime). |
| `skills` | array | Ordered array of skill objects. Empty if no skills matched. Order reflects match confidence where multiple skills fire; the runtime should concatenate bodies in this order. |
| `config` | object | Organisation configuration. Always present, regardless of whether skills matched. |
| `audit.org_id` | string | The organisation identifier resolved from the API key. |
| `audit.caller_key_id` | string | An opaque identifier for the API key used. Never the key itself. |
| `audit.user_id` | string or null | The resolved user identifier from the identity token, if present. |
| `audit.resolved_role` | string or null | The role the management layer resolved from the identity token. Null if no identity was provided or in single-user deployments. |
| `audit.permission_tier` | string | The highest classification level the user was permitted to access for this request. One of: `public`, `internal`, `confidential`. |
| `audit.query_hash` | string | SHA-256 hash of the query string. Allows audit verification without storing the raw query in the management layer. |
| `audit.skill_versions` | array | The name and exact version of every skill that fired. The immutable record for audit: the precise skill content that governed this response. |
| `audit.timestamp` | string | ISO 8601 timestamp of when the management layer processed the request. |

---

## Skill object

Each item in the `skills` array:

```json
{
  "name": "string",
  "version": "string",
  "description": "string",
  "body": "string",
  "tags": ["string"],
  "owner": "string",
  "execution_hints": {
    "locks_session": true | false,
    "lock_release_signals": ["string"] | null,
    "cancel_phrases": ["string"] | null,
    "ui_theme": { <theme object> } | null
  },
  "approved_by": "string | null",
  "approved_at": "string (ISO 8601) | null",
  "classification": "public | internal | confidential | null"
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | The skill's unique kebab-case identifier. |
| `version` | string | Exact semver of the approved version in force at the time of this request. Immutable for audit. |
| `description` | string | One-sentence description of what the skill does. |
| `body` | string | The full skill body, to be injected verbatim into the LLM system prompt. |
| `tags` | array | Tag vocabulary from the Score spec. |
| `owner` | string | The person responsible for this skill. |
| `execution_hints.locks_session` | boolean | If `true`, the runtime should enter session-lock mode for this skill. |
| `execution_hints.lock_release_signals` | array or null | Phrases that release a session lock. Null if `locks_session` is false. |
| `execution_hints.cancel_phrases` | array or null | Phrases that cancel a locked flow and return to normal mode. |
| `execution_hints.ui_theme` | object or null | Branding theme object for interface customisation. Null if not set. |
| `approved_by` | string or null | Identifier of the approver. Present if the governance layer has approval workflows active. Null in configurations without formal approval. |
| `approved_at` | string or null | ISO 8601 timestamp of approval. |
| `classification` | string or null | Data classification of this skill. One of `public`, `internal`, `confidential`. Null if not set. The runtime should use this to determine LLM routing – `confidential` skills must not be sent to a cloud LLM. |

---

## Config object

```json
{
  "org_id": "string",
  "org_name": "string",
  "honesty_protocol": {
    "enabled": true | false,
    "org_signal_phrases": ["string"],
    "refusal_message": "string"
  },
  "llm_routing": {
    "default": "local | cloud",
    "confidential_override": "local",
    "local_model": "string | null",
    "cloud_model": "string | null"
  },
  "interfaces": {
    "telegram": { "enabled": true | false },
    "slack": { "enabled": true | false },
    "teams": { "enabled": true | false },
    "api": { "enabled": true | false }
  },
  "branding": {
    "assistant_name": "string",
    "logo_url": "string | null",
    "theme": { <theme object> } | null
  },
  "score_version": "string"
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `org_id` | string | Unique organisation identifier. |
| `org_name` | string | Display name of the organisation. |
| `honesty_protocol.enabled` | boolean | Whether the honesty protocol is active. Should always be `true` in production. |
| `honesty_protocol.org_signal_phrases` | array | Phrases that indicate an organisational query. Used by the runtime to determine whether a zero-match response should trigger the honesty protocol or fall through to the general LLM. |
| `honesty_protocol.refusal_message` | string | The configured message to return when the honesty protocol fires. |
| `llm_routing.default` | string | Default routing for queries without a classification override. `local` or `cloud`. |
| `llm_routing.confidential_override` | string | Always `local`. `confidential`-classified skills must never route to a cloud model. Not configurable: a hard constraint. |
| `llm_routing.local_model` | string or null | Identifier of the local model in use (e.g. `ollama/llama3`). Null if no local model is configured. |
| `llm_routing.cloud_model` | string or null | Identifier of the cloud model in use (e.g. `claude-sonnet-4-6`). Null if no cloud model is configured. |
| `interfaces` | object | Which interfaces are enabled for this organisation. The runtime should refuse connections on disabled interfaces. |
| `branding.assistant_name` | string | The name of the assistant as presented to users. |
| `branding.logo_url` | string or null | URL of the organisation's logo for interface display. |
| `branding.theme` | object or null | UI theme object. Derived from the active brand skill if one is present in the library. |
| `score_version` | string | The Score format version the management layer is operating against. The runtime should warn if this does not match its own supported version. |

---

## Error responses

All errors follow a consistent structure:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "request_id": "string | null"
  }
}
```

### Error codes

| HTTP status | Code | Meaning |
|-------------|------|---------|
| 400 | `invalid_request` | The request body is malformed or missing required fields. |
| 401 | `unauthorised` | No `Authorization` header present, or the header is malformed. |
| 403 | `forbidden` | The API key is valid but does not have permission to access this resource. |
| 404 | `org_not_found` | The API key resolves to an organisation that does not exist or has been deactivated. |
| 422 | `query_too_long` | The query exceeds 4,000 characters. |
| 429 | `rate_limited` | Too many requests. The `Retry-After` header indicates when the runtime may retry. |
| 500 | `internal_error` | The management layer encountered an unexpected error. The `request_id` should be included when reporting this. |
| 503 | `unavailable` | The management layer is temporarily unavailable. The runtime should retry with exponential backoff. |

### Honesty protocol is not an error

A query that matches no skills and triggers the honesty protocol returns **HTTP 200** with `matched: false` and `gap_logged: true`. Not an error condition: the correct behaviour of a governed system. The runtime should return the `honesty_protocol.refusal_message` from config and not call any LLM.

HTTP 200 is used rather than 204 (No Content) or 404 because something is always returned: the config object, the audit metadata, and the gap flag. The runtime must read the response body regardless of whether skills matched – it needs the config to know what refusal message to show the user. A status code distinction would add no information that is not already in the response body, and would require runtimes to handle two code paths for what is fundamentally the same response shape. Developers expecting a 204 for zero-match cases should note that this API has no 204 response – all successful requests return 200 with a full response body.

---

## Versioning behaviour

### What the runtime receives

The context API always returns the current approved version of each skill. The runtime has no mechanism to request a previous version. The governance layer determines what is live; the runtime executes what it is given. The design is intentional.

### What is logged

The `audit.skill_versions` array in the response records the exact name and version of every skill that fired. The runtime must log this alongside the `request_id`, the `metadata.timestamp` from the request, and the response it generated. Together these form The Recording entry for this execution event.

### Why the runtime cannot choose a version

Allowing a runtime to request a specific skill version would allow it to bypass the approval workflow. A skill at version `0.1.3` may have been superseded by `0.1.4` precisely because `0.1.3` contained an error or an unapproved claim. If the runtime could pin to `0.1.3`, the governance layer's approval of `0.1.4` would have no practical effect.

The governance layer owns what is live. The runtime executes what is live. The version in the audit log is evidence of what governed the response – not a choice available to the caller.

### Format versioning

The API itself is versioned at the URL level (`/v1/`). A future breaking change to the request or response schema will be introduced at `/v2/` with a documented migration period. The `score_version` field in the config object identifies the Score format version the management layer is operating against – separate from the API version.

---

## Implementing a Score-compatible runtime

A runtime is Score-compatible if it correctly implements the following behaviours against this API.

### Startup sequence

1. Call `GET /v1/health` to verify connectivity. Fail loudly if the management layer is unreachable – do not start in a degraded state that silently skips governance.
2. Make an initial `POST /v1/context` call with an empty query to retrieve the config object. Cache the config for the session.
3. Log the `score_version` from config. Warn if it does not match the runtime's supported Score version.

### Query handling

For every incoming user query:

1. Call `POST /v1/context` with the query and session metadata.
2. If `matched` is `true`: concatenate the `body` fields of all returned skills in order. Inject the concatenated body as the system prompt. Call the LLM specified by `llm_routing`, respecting the `classification` of each skill – any `confidential` skill routes the entire query to the local model, regardless of the default routing setting.
3. If `matched` is `false` and `gap_logged` is `true`: return the `honesty_protocol.refusal_message` from config. Do not call any LLM. A Score-compatible runtime does not hallucinate on organisational queries. Hard constraint, not a configuration option.
4. If `matched` is `false` and `gap_logged` is `false`: the query contains no organisational signal. Route to the general fallback LLM as configured.

### Recording entries

For every context API call, the runtime must write a Recording entry containing at minimum:

```json
{
  "request_id": "<from context API response>",
  "session_id": "<from request>",
  "interface": "<from request>",
  "user_id": "<from request metadata>",
  "query_hash": "<from audit object in response>",
  "skill_versions": "<from audit object in response>",
  "llm_routed_to": "local | cloud | none",
  "honesty_protocol_fired": true | false,
  "runtime_timestamp": "<ISO 8601>",
  "management_timestamp": "<from audit.timestamp in response>"
}
```

The raw query and response must not be stored in The Recording by default – only the hash of the query and the metadata of the execution event. Organisations that require full query/response logging for regulatory purposes may configure this separately, subject to their own data governance policies.

### Session management

If a skill sets `execution_hints.locks_session` to `true`, the runtime must:

1. Enter session-lock mode: subsequent queries in the session bypass trigger matching and continue to use the locked skill's body until a release signal is received.
2. Monitor incoming messages for phrases matching `execution_hints.lock_release_signals`. On match, exit session-lock mode and resume normal context API calls.
3. Monitor for `execution_hints.cancel_phrases`. On match, exit session-lock mode immediately without completing the locked flow.

Session lock state is managed by the runtime, not the management layer. The runtime does not need to call the context API on every locked-session message – it already has the skill body.

### Error handling

- On `401` or `403`: fail loudly. Do not proceed without valid authentication.
- On `429`: retry after the `Retry-After` interval. Do not surface the error to the user during this wait – queue the query if the interface supports it.
- On `500` or `503`: retry with exponential backoff (suggested: 1s, 2s, 4s, then fail). Log the `request_id` if present. Surface a neutral error to the user after three failed retries – do not attempt to respond without governance.
- On `503` at startup: do not start. A runtime that cannot reach its governance layer must not operate.

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 0.1.1 | April 2026 | Added `identity` object to request schema (user identity token, token type, user_id, role, department, verified_by). Added `resolved_role`, `permission_tier`, and `user_id` to audit object in response. Added permission architecture section (role-based context partitioning, two-tier LLM routing). Added identity resolution section. Added "management layer is the trust boundary" design principle. |
| 0.1.0 | April 2026 | Initial specification. |
