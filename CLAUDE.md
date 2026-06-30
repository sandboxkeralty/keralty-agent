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

# Test chat endpoint
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

Default locale is `es`. Routes are `app/[locale]/page.tsx` etc. — the Next.js middleware handles locale routing.

### Build & deploy to Cloud Run

```bash
# Build backend for linux/amd64 (required — local machines are arm64)
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/keralty-agent-backend:TAG \
  ./backend
docker push us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/keralty-agent-backend:TAG
gcloud run deploy keralty-agent-backend \
  --image us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/keralty-agent-backend:TAG \
  --region us-central1 --project keraltysandbox --quiet

# Frontend requires NEXT_PUBLIC_API_URL at build time (not runtime)
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/keralty-agent-frontend:TAG \
  --build-arg NEXT_PUBLIC_API_URL=https://keralty-agent-backend-569920970367.us-central1.run.app \
  --build-arg NEXT_PUBLIC_ADMIN_ENABLED=true \
  ./frontend
```

`cloudbuild.yaml` (repo root) and `infra/cloudbuild.yaml` automate this via Cloud Build. The `infra/cloudrun-*.yaml` files are YAML spec stubs (currently empty).

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
            ├─ EditingAgent      (gemini-2.5-flash) — edits existing Docs (HITL gated)
            ├─ ReviewAgent       (gemini-2.5-flash) — QA review before approval
            ├─ VisualAgent       (gemini-2.5-pro)   — Google Slides + Imagen 3
            ├─ EmailAgent        (gemini-2.5-pro)   — Gmail read/draft/send
            └─ KnowledgeAgent    (gemini-2.5-flash) — corporate KB (stub tools)
```

All agents live in `backend/agents/`. The orchestrator's `INSTRUCTION` block in `orchestrator.py` contains the routing rules — **edit this when adding capabilities or fixing misdirected requests**.

### Human-in-the-loop (HITL) approval

Any write to Google Workspace goes through `approval_create` (in `tools/approval_tools.py`), which creates a Firestore task with `status: "pending"`. The frontend polls `GET /api/tasks` and renders `ApprovalCard` components. `POST /api/tasks/{id}/approve` marks it approved in Firestore — **but the ADK runner resume is not yet wired** (see the TODO comment in `routers/tasks.py`). Similarly, `docs_update` and `slides_update` also create HITL tasks rather than writing directly.

### SSE streaming

`routers/chat.py` streams ADK events as `text/event-stream`. A known issue: ADK `Part` objects always have a `.text` attribute (it's a Pydantic field defaulting to `None`), so the guard must be `if p.text is not None:` — **not** `if hasattr(p, "text"):`.

### Authentication (current state)

The middleware (`auth/auth_middleware.py`) accepts any `Bearer` token and hardcodes `sandbox-user`. A full OAuth flow is planned (`docs/oauth-implementation-plan.md`) but not yet implemented. The `/auth/login` redirect to Google works; the callback stores nothing.

### Google Workspace API access

All service factories (`services/drive.py`, `docs.py`, `sheets.py`, `slides.py`) currently use `google.auth.default()` (service account ADC). User-scoped Workspace operations fail until the OAuth token injection plan is implemented. The OAuth Client ID is `569920970367-rfjpqnh8sbs973bromqa8rm526htp381.apps.googleusercontent.com`.

### Feature flags

Controlled via `config.py` / env vars: `USE_VERTEX_AI`, `USE_RAG_ENGINE`, `USE_AGENT_ENGINE`, `USE_LIVEKIT`, `SEARCH_GROUNDING_ENABLED`, `ADMIN_PANEL_ENABLED`, `KB_AGENT_ENABLED`, `EMAIL_GMAIL_ENABLED`. Most are `false` in the deployed sandbox.

### Observability

- Tracing: OpenTelemetry → Cloud Trace (toggle `OTEL_ENABLED=true`)
- Logging: Cloud Logging when `ENVIRONMENT != development`
- Alerts: `deploy/monitoring/alerts.yaml` defines thresholds for cost, error rate, latency P99, Gemini rate limits, pending approvals

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
| HITL resume | `routers/tasks.py` line 25 | TODO comment, not wired to ADK |
| i18n backend | `backend/i18n/` | Empty stubs |
| IAP auth | `backend/auth/iap.py` | Empty stub |

---

## GCP infrastructure

- **Project**: `keraltysandbox`
- **Region**: `us-central1`
- **Artifact Registry**: `us-central1-docker.pkg.dev/keraltysandbox/cloud-run-source-deploy/`
- **Firestore**: default database — collections: `users`, `sessions`, `messages`, `tasks`, `audit_events`
- **GCS bucket**: `keralty-agent-dev-artifacts`
- **Active account**: `sandboxkeralty@gmail.com`

Enabled APIs: Drive, Docs, Sheets, Slides, Gmail, Vertex AI, Gemini, Firestore, Cloud Run, Artifact Registry, Cloud Build, Logging, Monitoring, Trace.

---

## i18n

Frontend uses `next-intl` with locales `en` and `es` (default `es`). Message files are at `frontend/messages/{en,es}.json`. The middleware at `frontend/middleware.ts` handles locale prefixing for all non-API routes.
