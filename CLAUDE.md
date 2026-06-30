# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What this is

Keralty Assistant — a multi-agent AI system for Keralty (international healthcare company) built on **Google ADK** (Agent Development Kit). An orchestrator agent routes user requests to 8 specialised sub-agents that work with Google Workspace (Drive, Docs, Sheets, Slides, Gmail) and a corporate Knowledge Base. Deployed on Google Cloud Run (`keraltysandbox` GCP project, `us-central1`).

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

The venv is `backend/venv/` (Python 3.9). The live backend is deployed at:
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
  └─ ADK Runner (InMemorySessionService)
       └─ OrchestratorAgent  ← gemini-2.5-flash
            ├─ AnalysisAgent     (gemini-2.5-pro)  — reads Drive/Sheets, RAG
            ├─ ResearchAgent     (gemini-2.5-flash) — web search + Drive
            ├─ WritingAgent      (gemini-2.5-pro)   — drafts docs, creates Sheets/Docs
            ├─ EditingAgent      (gemini-2.5-flash) — edits existing Docs
            ├─ ReviewAgent       (gemini-2.5-flash) — QA review
            ├─ VisualAgent       (gemini-2.5-pro)   — Google Slides + Imagen 3
            ├─ EmailAgent        (gemini-2.5-pro)   — Gmail read/draft/send
            └─ KnowledgeAgent    (gemini-2.5-flash) — corporate KB (stub tools)
```

All agents live in `backend/agents/`. The orchestrator's `INSTRUCTION` block in `orchestrator.py` contains the routing rules — **edit this when adding capabilities or fixing misdirected requests**.

### Authentication & OAuth flow

Full OAuth is implemented and working:

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
- `backend/routers/chat.py` — loads Firestore creds, injects into ADK session state
- `backend/tools/_auth.py` — `_credentials(tool_context)` helper used by all Workspace tools
- `frontend/components/layout/Navbar.tsx` — captures `?token=`, shows login/logout

### Google Workspace API access

All four service factories (`services/drive.py`, `docs.py`, `sheets.py`, `slides.py`) accept an optional `credentials` parameter. When a user is logged in, their OAuth tokens flow from Firestore → session state → `_credentials(tool_context)` → service call. When not logged in (e.g. `test-token`), falls back to `google.auth.default()` (service account ADC — only works for files owned by the service account).

Required Cloud Run env vars: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `SECRET_KEY`.

### WritingAgent document creation

`WritingAgent` has both `docs_create` and `docs_update` in its toolset. The agent instruction explicitly tells it to always pass `content=` to `docs_create` so documents are never created empty. `docs_update` writes directly via `DocsService.append_text()` — no HITL queue.

### SSE streaming

`routers/chat.py` streams ADK events as `text/event-stream`. ADK `Part` objects always have a `.text` attribute (Pydantic field defaulting to `None`), so the guard must be `if p.text is not None:` — **not** `if hasattr(p, "text"):`.

Chat messages are rendered as Markdown in the frontend using `react-markdown` + `remark-gfm`, so agent responses with links, tables, headings and lists display correctly.

### Feature flags

Controlled via `config.py` / env vars: `USE_VERTEX_AI`, `USE_RAG_ENGINE`, `USE_AGENT_ENGINE`, `USE_LIVEKIT`, `SEARCH_GROUNDING_ENABLED`, `ADMIN_PANEL_ENABLED`, `KB_AGENT_ENABLED`, `EMAIL_GMAIL_ENABLED`. Most are `false` in the deployed sandbox. `GOOGLE_GENAI_USE_VERTEXAI=1` must be set in Cloud Run for ADK to use Vertex AI (without it, ADK requires `GOOGLE_API_KEY`).

### Observability

- Tracing: OpenTelemetry → Cloud Trace (toggle `OTEL_ENABLED=true`)
- Logging: Cloud Logging when `ENVIRONMENT != development`
- Alerts: `deploy/monitoring/alerts.yaml` defines thresholds for cost, error rate, latency P99, Gemini rate limits

---

## Key implementation gaps (stubs not yet wired)

| Component | File | Status |
|---|---|---|
| Knowledge Base tools | `tools/kb_tools.py` | All return empty/mock data |
| Email tools | `tools/email_tools.py` | All return empty/mock data |
| Gmail provider | `services/email/gmail_provider.py` | Empty stub |
| Voice WebSocket | `routers/voice.py` | Mock only |
| Image generation | `tools/image_tools.py` | Returns placeholder URL |
| History endpoints | `routers/history.py` | Returns empty lists |
| HITL resume | `routers/tasks.py` line 25 | TODO — not wired to ADK runner; approval_create in `tools/approval_tools.py` creates Firestore tasks but resume never fires |
| i18n backend | `backend/i18n/` | Empty stubs |
| IAP auth | `backend/auth/iap.py` | Empty stub |

---

## GCP infrastructure

- **Project**: `keraltysandbox`
- **Region**: `us-central1`
- **Artifact Registry**: `us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/`
- **Firestore**: default database (`us-central1`) — collections: `users` (stores google_credentials), `sessions`, `messages`, `tasks`, `audit_events`
- **GCS bucket**: `keralty-agent-dev-artifacts`
- **Active GCP account**: `sandboxkeralty@gmail.com`
- **GitHub repo**: `https://github.com/sandboxkeralty/keralty-agent.git` — push as user `sandboxkeralty` (`gh auth switch --user sandboxkeralty`)

Enabled APIs: Drive, Docs, Sheets, Slides, Gmail, Vertex AI, Gemini, Firestore, Cloud Run, Artifact Registry, Cloud Build, Logging, Monitoring, Trace.

---

## i18n

Frontend uses `next-intl` with locales `en` and `es` (default `es`). Message files are at `frontend/messages/{en,es}.json`. The middleware at `frontend/middleware.ts` handles locale prefixing for all non-API routes.
