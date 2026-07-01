# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What this is

Keralty Assistant — a multi-agent AI system for Keralty (international healthcare company) built on **Google ADK** (Agent Development Kit). An orchestrator agent routes user requests to 8 specialised sub-agents that work with Google Workspace (Drive, Docs, Sheets, Slides, Gmail) and a corporate Knowledge Base with full hybrid RAG. Deployed on Google Cloud Run (`keraltysandbox` GCP project, `us-central1`).

---

## Development commands

### Backend (FastAPI + Python)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run locally
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Health check
curl http://localhost:8000/health

# Test chat endpoint (test-token falls back to sandbox-user identity)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"message": "hello", "session_id": "dev-1", "user_id": "dev-user"}'
```

The venv is `backend/venv/` (Python 3.11 — Dockerfile uses `python:3.11-slim`). The live backend is deployed at:
`https://keralty-agent-backend-569920970367.us-central1.run.app`

### Frontend (Next.js 15 + TypeScript)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000 with Turbopack
npm run build
npm run lint
```

The live frontend is at:
`https://keralty-agent-frontend-569920970367.us-central1.run.app`

Default locale is `es`. Routes are `app/[locale]/page.tsx`. The Next.js middleware handles locale prefixing. `AppShell` (sidebar + navbar) is wired into `app/[locale]/layout.tsx`.

### Build & deploy to Cloud Run

```bash
# Build backend for linux/amd64 (required — local machines are arm64)
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/keralty-agent-backend:TAG \
  ./backend
docker push us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/keralty-agent-backend:TAG
gcloud run services update keralty-agent-backend \
  --image us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/keralty-agent-backend:TAG \
  --region us-central1 --project keraltysandbox --quiet

# Frontend requires NEXT_PUBLIC_API_URL at build time (not runtime)
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/keralty-agent-frontend:TAG \
  --build-arg NEXT_PUBLIC_API_URL=https://keralty-agent-backend-569920970367.us-central1.run.app \
  --build-arg NEXT_PUBLIC_ADMIN_ENABLED=true \
  ./frontend
docker push ... && gcloud run services update keralty-agent-frontend --image ... --region us-central1 --project keraltysandbox --quiet
```

When updating Cloud Run env vars that contain commas (e.g. `ALLOWED_ORIGINS`), use `^|^` as the custom delimiter:
```bash
gcloud run services update keralty-agent-backend \
  --update-env-vars "^|^ALLOWED_ORIGINS=https://frontend.run.app,http://localhost:3000"
```

---

## Architecture

### Agent pipeline (backend)

```
User message → POST /api/chat (SSE stream)
  └─ ADK Runner (FirestoreSessionService — persists across cold starts)
       └─ OrchestratorAgent  ← gemini-2.5-flash
            ├─ AnalysisAgent     (gemini-2.5-pro)  — reads Drive/Sheets, hybrid RAG
            ├─ ResearchAgent     (gemini-2.5-flash) — Google Search + Drive
            ├─ WritingAgent      (gemini-2.5-pro)   — drafts docs, creates Sheets/Docs
            ├─ EditingAgent      (gemini-2.5-flash) — edits existing Docs (HITL)
            ├─ ReviewAgent       (gemini-2.5-flash) — QA review
            ├─ VisualAgent       (gemini-2.5-pro)   — Google Slides + Imagen 3 (HITL)
            ├─ EmailAgent        (gemini-2.5-pro)   — Gmail read/draft/send (HITL)
            └─ KnowledgeAgent    (gemini-2.5-flash) — corporate KB via hybrid RAG
```

All agents live in `backend/agents/`. The orchestrator's `INSTRUCTION` block in `orchestrator.py` contains the routing rules — **edit this when adding capabilities or fixing misdirected requests**.

### Authentication & OAuth flow

```
Browser → GET /auth/login → Google consent
       ← redirect to /auth/callback?code=...
         exchange code for tokens (PKCE: flow cached by state in _flow_cache)
         verify id_token → get user email
         store google_credentials dict in Firestore users/{email}
         mint 7-day JWT (python-jose, SECRET_KEY env var)
       ← redirect to frontend /es?token=xxx
         Navbar captures token → localStorage
         ChatWindow reads token → Authorization: Bearer {jwt}
POST /api/chat → middleware verifies JWT → request.state.user = {uid, email}
              → load google_credentials from Firestore
              → inject into ADK session.state["google_credentials"]
              → tool_context.state["google_credentials"] available in all tools
```

Key files:
- `backend/auth/google_oauth.py` — OAuth flow helpers + `_flow_cache` (PKCE state preservation)
- `backend/auth/auth_middleware.py` — JWT verification; falls back to `sandbox-user` for `test-token`
- `backend/routers/auth.py` — `/auth/login` and `/auth/callback`
- `backend/routers/chat.py` — loads Firestore creds, injects into ADK session state; also persists messages
- `backend/tools/_auth.py` — `_credentials(tool_context)` helper: extracts creds, refreshes if expired, re-persists to Firestore
- `frontend/components/layout/Navbar.tsx` — captures `?token=`, shows login/logout

### Google Workspace API access

All four service factories (`services/drive.py`, `docs.py`, `sheets.py`, `slides.py`) accept an optional `credentials` parameter. When a user is logged in, their OAuth tokens flow from Firestore → session state → `_credentials(tool_context)` → service call. When not logged in (e.g. `test-token`), falls back to `google.auth.default()` (service account ADC — only works for files owned by the service account).

Required Cloud Run env vars: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `SECRET_KEY`.

**Token auto-refresh**: `tools/_auth.py` checks `creds.expired`, calls `creds.refresh(GRequest())`, and re-persists updated tokens to Firestore. No silent 401s.

**Note**: `routers/documents.py` (`GET /documents/`) does not thread user credentials — it uses ADC only. Files listed via this endpoint must be accessible by the service account.

### HITL (Human-in-the-Loop) approval flow

EditingAgent, VisualAgent, and EmailAgent all use a conversational HITL pattern:

1. Agent proposes changes → calls `approval_create` → Firestore task with `status=pending`
2. `routers/chat.py` SSE stream includes a `pending_approval` event with `task_id`
3. `ChatWindow.tsx` polls `GET /api/tasks` every 5 seconds while idle; renders `<ApprovalCard>` for each pending task
4. User clicks Approve → frontend calls `POST /api/tasks/{id}/approve` → auto-sends `"[APROBADO] task_id={id}"` chat message
5. Agent instruction watches for `[APROBADO] task_id=...` and executes the buffered action

Guardrail in each agent instruction: **NUNCA ejecutes la acción destructiva sin [APROBADO]**.

### Voice pipeline

```
Browser mic (getUserMedia 16 kHz mono)
  → AudioContext → AudioWorkletNode (public/audio-processor.js)
    → Float32→Int16 PCM conversion
    → base64-encode → WebSocket ws://.../voice/stream
      → backend: routers/voice.py
        → Gemini Live API (gemini-live-2.5-flash, TEXT modality — the
          "-native-audio" model variant only supports AUDIO output and
          rejects TEXT modality outright)
        ← transcript text
      → WebSocket → VoiceChat.tsx accumulates transcript
        → onTranscript callback → ChatWindow sets input + auto-submits form
```

Key files: `frontend/components/chat/VoiceChat.tsx`, `frontend/public/audio-processor.js`, `backend/routers/voice.py`.

### RAG / Knowledge Base pipeline

Full 6-stage hybrid RAG in `backend/services/rag/`:

1. **Multi-query expansion** (`pipeline.py`): Gemini generates 3 semantic query variants
2. **Hybrid retrieval** (`retriever.py`): BM25 sparse (rank-bm25) + Vertex AI text-embedding-005 dense cosine similarity, fused via Reciprocal Rank Fusion across all query variants
3. **Neighbor expansion**: pulls ±1 adjacent chunks for top-20 fused results
4. **Gemini reranker** (`reranker.py`): scores each passage 0.0–1.0; dynamic gap cutoff (stops when `prev−curr > 0.2` and `len ≥ 4`); recall preservation adds back high-RRF items if result < min_k
5. **Abstention gate** (`pipeline.py`): concept-recall check (keyword coverage of query terms in retrieved text); abstains with follow-up suggestions if coverage < 0.5
6. **Context assembly**: `[[filename:pN]]` citation blocks; `RAGResult` dataclass with `should_abstain`, `context_text`, `citations`, `coverage`

Chunking (`chunker.py`): structure-aware paragraph split → greedy merge (max 1000 tokens) → 15% overlap → coalesce < 120 tokens → neighbor links.

Embeddings (`embedder.py`): Vertex AI `text-embedding-005`, batch size 250, `RETRIEVAL_DOCUMENT` task type for indexing, `RETRIEVAL_QUERY` for queries.

Storage (`store.py`): Firestore `kb_chunks` collection (embedding arrays as List[float]), `kb_documents` collection for metadata.

Ingestion (`ingestion.py`): accepts PDF (pypdf), DOCX (python-docx), CSV (csv.DictReader), TXT/MD. GCS upload of originals to `keralty-agent-dev-artifacts`. Cache invalidated after every ingestion.

Ingestion endpoint: `POST /knowledge/documents` (50 MB limit, admin-gated). Management: `GET /knowledge/documents`, `DELETE /knowledge/documents/{doc_id}`.

**Generation guardrails E10–E16** (chain-of-verification, entity consistency, timeline checks, numeric tools) are **delegated to agent prompt instructions**, not implemented as code.

### Gmail / Email agent

`services/email/gmail_provider.py` — full implementation using `googleapiclient.discovery.build("gmail", "v1", ...)`:
- `list_threads` — label filter, metadata headers
- `get_thread` — recursive MIME parser, prefers text/plain
- `search_threads` — Gmail query syntax
- `create_draft` — with optional thread_id for replies
- `send_draft`, `get_draft`

`tools/email_tools.py` — all 9 functions call `GmailProvider` with `_credentials(tool_context)`. `email_track` writes to Firestore `email_tracking`. EmailAgent has mandatory HITL before `email_send`.

### Google Slides write operations

`services/slides.py` — real Slides batchUpdate API:
- `add_slide_with_content(presentation_id, title, body, speaker_notes, credentials)` — creates `TITLE_AND_BODY` slide with `placeholderIdMappings`, inserts text in same batch; speaker notes in a second batch call
- `insert_image(presentation_id, slide_id, image_url, ...)` — `createImage` with EMU coordinates
- `get_presentation(presentation_id, credentials)` — raw API response

`tools/slides_tools.py`:
- `slides_create(title, outline=None)` — creates presentation; if `outline` is a JSON array `[{title, body}]`, populates all slides in one call
- `slides_add_slide(presentation_id, slide_title, body, speaker_notes=None)` — adds one slide
- `slides_add_image(presentation_id, slide_id, image_url)` — inserts image
- `slides_get(presentation_id)` — returns `{slides: [{slide_id, title}]}`

### Imagen 3 (image generation)

`tools/image_tools.py` — calls `vertexai.preview.vision_models.ImageGenerationModel` with `IMAGEN_MODEL` (default `imagen-3.0-generate-001`). Uploads result bytes to GCS `keralty-agent-dev-artifacts/images/`, makes blob public, returns public URL. Falls back to placeholder URL on any error.

### Session persistence & history

`backend/services/adk_session_service.py` (FirestoreSessionService) — ADK `BaseSessionService` backed by Firestore `adk_sessions` collection. Survives Cloud Run cold starts.

`routers/chat.py` persists every user message and agent response to Firestore `messages` collection after each turn.

`routers/history.py`:
- `GET /history/` — all sessions for the authenticated user, with message count and 120-char preview
- `GET /history/{session_id}` — full message thread (ownership-checked)
- `DELETE /history/{session_id}` — deletes session (messages retained for audit)

Frontend: `frontend/app/[locale]/history/page.tsx` — two-column layout: session list + message thread.

### Admin panel

`frontend/app/[locale]/admin/page.tsx` — 5 tabs, all fetching live backend data:
- **Métricas**: 4 stat cards (sessions, messages, users, audit events) from `GET /admin/metrics`
- **Usuarios**: user table with avatar, role badge, last activity from `GET /admin/users`; `PATCH /admin/users/{email}` for name/role edits
- **Knowledge Base**: file upload → `POST /knowledge/documents`; indexed documents table with delete
- **Auditoría**: color-coded action badges from `GET /admin/audit`
- **Configuración**: feature flag badges from `GET /admin/configs` (read-only)

All admin endpoints gated on `ADMIN_PANEL_ENABLED=true`.

### DocumentPicker in chat

Paperclip button in `ChatWindow.tsx` opens `<DocumentPicker>` modal (component at `components/documents/DocumentPicker.tsx`). Selected file text is fetched from `GET /documents/{file_id}/text` and sent as `attached_context` in the chat request body. `routers/chat.py` injects it into `session.state["attached_documents"]` before running the agent.

### SSE streaming

`routers/chat.py` streams ADK events as `text/event-stream`. ADK `Part` objects always have a `.text` attribute (Pydantic field defaulting to `None`), so the guard must be `if p.text is not None:` — **not** `if hasattr(p, "text"):`.

Chat messages are rendered as Markdown in the frontend using `react-markdown` + `remark-gfm`, so agent responses with links, tables, headings and lists display correctly.

### Feature flags

Controlled via `config.py` / env vars:

| Flag | Default | Purpose |
|---|---|---|
| `ADMIN_PANEL_ENABLED` | `false` | Enables admin routes + UI |
| `KB_AGENT_ENABLED` | `true` | KnowledgeAgent active |
| `EMAIL_GMAIL_ENABLED` | `true` | Gmail tools active |
| `EMAIL_SEND_ENABLED` | `true` | Allows email_send tool |
| `VOICE_ENABLED` | `true` | Voice WebSocket active |
| `SLIDES_ENABLED` | `true` | Slides tools active |
| `IMAGE_GEN_ENABLED` | `true` | Imagen 3 active |
| `SEARCH_GROUNDING_ENABLED` | `false` | Vertex AI Search grounding |
| `USE_VERTEX_AI` | `false` | Route ADK through Vertex AI |
| `OTEL_ENABLED` | `false` | OpenTelemetry tracing |

`GOOGLE_GENAI_USE_VERTEXAI=1` must be set in Cloud Run for ADK to use Vertex AI (without it, ADK requires `GOOGLE_API_KEY`).

RAG pipeline knobs in `config.py`: `RAG_CHUNK_TARGET_TOKENS` (800), `RAG_CHUNK_MAX_TOKENS` (1000), `RAG_CHUNK_OVERLAP_PCT` (0.15), `RAG_CHUNK_MIN_TOKENS` (120), `RAG_K_DENSE` (30), `RAG_K_SPARSE` (30), `RAG_K_FUSED` (20), `RAG_RERANK_TOP_K` (8), `RAG_REWRITE_COUNT` (3), `RAG_NEIGHBOR_WINDOW` (1), `RAG_ABSTAIN_THRESHOLD` (0.5), `RAG_EMBED_MODEL` (`text-embedding-005`).

### Observability

- Tracing: OpenTelemetry → Cloud Trace (toggle `OTEL_ENABLED=true`)
- Logging: Cloud Logging when `ENVIRONMENT != development`
- Alerts: `deploy/monitoring/alerts.yaml` defines thresholds for cost, error rate, latency P99, Gemini rate limits

---

## Known stubs / unimplemented areas

| Component | File | Status |
|---|---|---|
| IAP authentication | `backend/auth/iap.py` | Empty stub — not needed unless deploying behind Cloud IAP |
| Backend i18n | `backend/i18n/` | All three files empty — frontend uses `next-intl` independently; backend never sends localised strings |
| Email dashboard page | `frontend/app/[locale]/email/page.tsx` | UI shell — navigation and empty states work, but inbox/tracking data never populates from API; email functionality flows through the chat interface |
| Audit logging — slides & KB | `tools/slides_tools.py`, `routers/knowledge.py` | `slides_create` and KB document ingestion are not logged to `audit_events`; all other write operations (docs, email, HITL) are |
| RAG generation guardrails E10–E16 | _(no code file)_ | Chain-of-verification, entity consistency, timeline/numeric checks delegated to agent prompt instructions, not implemented as callable tools |
| Outlook email provider | `backend/services/email/outlook_provider.py` | Empty stub — Azure OAuth vars defined in config but provider not implemented |
| Email package scaffolding | `backend/services/email/{__init__,base,factory}.py` | All empty — only `gmail_provider.py` is implemented |
| Legacy email stub | `backend/services/email.py` | 49-line stub GmailProvider returning mocks — **not imported anywhere** (superseded by `services/email/gmail_provider.py`); safe to delete |
| Legacy service stubs | `backend/services/{knowledge_base,storage,voice}.py` | All empty, not imported anywhere — scaffolding left over from early design |
| Vertex AI utility | `backend/services/vertex_ai.py` | Minimal: `init_vertex_ai()` and `get_grounding_tool()` — called only if `USE_VERTEX_AI=true` / `SEARCH_GROUNDING_ENABLED=true` |

---

## GCP infrastructure

- **Project**: `keraltysandbox`
- **Region**: `us-central1`
- **Artifact Registry**: `us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/`
- **Firestore**: default database (`us-central1`) — collections:
  - `users` — OAuth credentials (google_credentials field), user profile
  - `adk_sessions` — ADK session state (FirestoreSessionService)
  - `messages` — chat message history
  - `sessions` — session metadata + preview
  - `tasks` — HITL approval tasks (pending/approved/rejected)
  - `audit_events` — write operation audit trail
  - `email_tracking` — follow-up tracking records
  - `kb_chunks` — RAG document chunks with 768-dim embedding arrays
  - `kb_documents` — RAG document metadata
- **Firestore composite indexes** (deployed): `email_tracking(user_id,status)`, `tasks(user_id,status,created_at)`, `messages(session_id,created_at)`, `sessions(user_id,created_at)`
- **GCS bucket**: `keralty-agent-dev-artifacts` — stores generated images (`images/`) and KB original files (`kb/`)
- **Active GCP account**: `sandboxkeralty@gmail.com`
- **GitHub repo**: `https://github.com/sandboxkeralty/keralty-agent.git` — push as user `sandboxkeralty` (`gh auth switch --user sandboxkeralty`)

Enabled APIs: Drive, Docs, Sheets, Slides, Gmail, Vertex AI, Gemini, Firestore, Cloud Run, Artifact Registry, Cloud Build, Logging, Monitoring, Trace.

---

## i18n

Frontend uses `next-intl` with locales `en` and `es` (default `es`). Message files are at `frontend/messages/{en,es}.json`. The middleware at `frontend/middleware.ts` handles locale prefixing for all non-API routes.

`backend/i18n/` exists as a scaffold but all files are empty — backend responses are in the agent's natural language (Spanish/English bilingual per orchestrator instruction).
