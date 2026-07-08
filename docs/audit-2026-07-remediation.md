# Codebase Audit & Remediation — July 2026

_A full read-only audit (backend core, backend services, frontend) was run against the
Keralty Assistant codebase to assess whether it is executive/production-grade. This document
records the **Critical + High** findings that were **fixed** in this cycle, and the
**Medium/Low** items **deferred** to a future cycle. It complements `CLAUDE.md` (which
documents the system as built) by tracking the security, data-integrity, and trust-grade
defects the audit surfaced beyond what `CLAUDE.md` already knew._

## Fixed this cycle (Critical + High)

### Auth (production-grade, no test-token)
- **Invalid/expired/forged JWT no longer authenticates as the sandbox user.**
  `auth/auth_middleware.py` now hard-401s on any decode/verify/expiry failure instead of
  falling back to `sandbox-user` (which holds real Drive + `gmail.modify` credentials). The
  `test-token` bypass is removed.
- **Frontend requires real login.** The `|| 'test-token'` fallback (11 sites) is gone; a new
  single API client (`frontend/lib/api.ts`) owns the token and base URL, and a new `AuthGate`
  (`components/layout/AuthGate.tsx`) shows an explicit login-required screen when logged out or
  on any 401, instead of silently operating as the sandbox identity.

### HITL approval — now enforced in code, not just prompt
- Destructive tools (`email_send`, `docs_update`, `update_spreadsheet_values`,
  `append_spreadsheet_values`) call `tools/_approval.py::_require_approval`, which verifies an
  **approved, user-owned, unconsumed** Firestore task for the exact resource and then consumes
  it (one approval → one execution, no replay). A `[APROBADO]` string inside an attached
  document can no longer trigger a send/write.
- `WritingAgent` no longer holds the ungated `docs_update` (edits now route to the gated
  `EditingAgent`).

### Data integrity
- **Token refresh no longer wipes the user's profile.** New
  `FirestoreService.update_credentials` writes only `google_credentials`; the three refresh
  call sites use it instead of `store_user_credentials(user_id, {}, ...)` (which wrote
  email/name/picture as null on every routine refresh).
- `attached_documents` session state is capped to the current turn (was appended unbounded,
  walking toward the Firestore 1 MB doc limit).

### RAG reactivation
- `_rewrite_queries` (query expansion) and `reranker.rerank` now set
  `thinking_config(thinking_budget=0)` and use the shared `get_genai_client()`. Both were
  silently degraded to no-ops in production (empty model output → `json.loads` "Expecting
  value"). Verified: query expansion now returns real variants.

### Drive robustness
- Drive `q` values are quote-escaped (`_escape_drive_query`) — fixes both injection and the
  "any apostrophe 400s the search" bug.
- `read_document_text` / `export_pdf` raise a typed `DriveReadError` instead of returning error
  **strings** that could be attached to the prompt as if they were document content.
- Size cap (50 MB) before `get_media` downloads in `drive.py` and `sheets.py` (was unbounded →
  OOM risk).

### Chat error UX
- Backend stops streaming raw `str(e)` to users; emits a structured `error` event and logs the
  detail server-side.
- Frontend checks `response.ok`, handles the `error` event, and shows a **translated** message
  (`chat.errorGeneric`) instead of an empty assistant bubble; hardcoded English error removed.

### Agent behaviour correctness
- KnowledgeAgent no longer claims to enforce a role system that doesn't exist.
- The duplicated `LÍMITES` block no longer lists each agent's own core job as out-of-scope
  (ResearchAgent/internet, WritingAgent/create-doc, VisualAgent/presentation).
- EmailAgent no longer claims Outlook / multi-account capability that isn't implemented.

### Frontend hardening
- 5s task poller pauses when logged out or the tab is hidden.
- Message IDs use `crypto.randomUUID()` (were `Date.now()` — collision/mis-targeted-stream risk).
- `next.config.ts` adds a CSP (locked `img-src`/`connect-src`/`frame-ancestors`, `object-src
  'none'`), `X-Frame-Options`, `Referrer-Policy`, and an `images.remotePatterns` allowlist.

### Deploy/build hygiene
- `requirements.txt` fully pinned to the working image's versions (esp. `google-adk`).
- `backend/.dockerignore` added (keeps `venv/`, `.env`, tests out of the image).
- `ENVIRONMENT=production` set on the Cloud Run backend (enables Cloud Logging; `/health` no
  longer reports `development`).

## Deferred to a future cycle (Medium / Low)

Tracked, intentionally out of scope this cycle:

- **HttpOnly-cookie auth** to remove the JWT from `localStorage` (XSS token-theft hardening).
  Blocked on a **shared custom domain** (`app.` / `api.keralty.com`) — cross-`run.app`-host
  cookies are third-party and browser-blocked. CSP added now is the interim mitigation.
- **Rate limiting** (none today) and the **unauthenticated, unthrottled `/voice` WebSocket**
  opening a billed Gemini Live session on connect.
- **RAG scalability**: `load_all_chunks` streams the entire `kb_chunks` collection into memory
  on cold start and builds a NumPy matrix over all embeddings per query (no vector index); the
  in-memory `_corpus_cache` is per-instance so ingestion only invalidates the serving instance
  (stale KB on other warm instances until cold start).
- **`_concept_recall` abstention gate** is naive substring matching (punctuation-sensitive,
  no word boundaries → EPS/IPS/POS false matches, no stemming/accents, thin stopword list).
- **`_flow_cache`** (OAuth PKCE) is process-local — breaks login across multiple instances and
  leaks memory for abandoned logins; needs a shared store with TTL.
- **Gmail parsing**: latin-1/Windows-1252 bodies become mojibake (always decoded UTF-8),
  HTML-only emails return raw tags, and `list_threads`/`search_threads` are N+1.
- **Docs Markdown rendering**: `docs.py` writes literal `##`/`**` into Google Docs (no
  Markdown→formatting conversion).
- **Credential-at-rest**: OAuth refresh tokens + client secret stored plaintext in Firestore
  (no KMS envelope encryption).
- **Admin metrics** (`get_metrics`) do four full-collection scans per call.
- **Accessibility**: no `aria-label`s on icon-only buttons; Sidebar delete control is
  keyboard-unreachable.
- **Dead code**: seven unused `components/email/*` + `components/chat/{KBSearchResult,
  OrgChartCard}.tsx`; the `services/email.py` legacy stub coexisting with the `services/email/`
  package.
- **Slides HITL**: `slides_create` remains prompt-gated only (approval task has no
  `document_id` at creation time, so the code gate can't key on it — needs a different scheme).
- Assorted Low: Drive `list_documents` ignores pagination; RRF `k_rrf=60` hardcoded;
  `?token=` in the OAuth redirect URL lands in server/referrer logs; SSE partial-message /
  network-drop handling; `LocaleSwitcher` drops query string.
