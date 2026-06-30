# Keralty Assistant — Development Gaps & Pending Work

_Last updated: 2026-06-30. Based on full codebase audit._

---

## Executive Summary

The core chat pipeline, Google OAuth, and Google Workspace write operations (Docs, Sheets, Drive) are working end-to-end. The 8-agent architecture is defined and the orchestrator routes correctly. However, approximately **60% of the advertised capabilities are stubs that return empty/fake data**, the Human-in-the-Loop approval system creates tasks but never executes them, the email and knowledge base agents have zero real implementation, and the voice interface is a mock WebSocket with no audio processing.

---

## What Is Working (Baseline)

| Capability | Status |
|---|---|
| ADK orchestrator + 8 sub-agent routing | ✅ Working |
| Google OAuth login → JWT → credential injection into agents | ✅ Working |
| Google Docs: create with content, read, append text | ✅ Working |
| Google Drive: list, search, read text, export PDF | ✅ Working |
| Google Sheets: create, read range, update values | ✅ Working |
| Google Slides: create empty presentation | ✅ Working (content writing blocked) |
| Chat SSE streaming with Markdown rendering | ✅ Working |
| Firestore database (tasks, users/credentials) | ✅ Working |
| Frontend: login/logout, locale switcher, sidebar | ✅ Working |
| Cloud Run deployment pipeline | ✅ Working |

---

## Gap 1 — Gmail / Email Agent (P0 — Core Feature)

**Current state:** Every single function in `tools/email_tools.py` is a stub returning empty arrays and fake IDs. `services/email/gmail_provider.py` is an empty file (1 line). The EmailAgent is running against these mocks, so asking it anything produces confident-sounding but completely fabricated responses.

**What needs to be built:**

### 1a. Gmail API service (`services/email/gmail_provider.py`)
Real implementation using the Gmail API with the user's OAuth credentials (same pattern as DriveService). Methods needed:
- `list_threads(max_results, folder)` — `users.threads.list`
- `get_thread(thread_id)` — `users.threads.get` with full message bodies
- `search_threads(query)` — `users.messages.list` with Gmail search syntax
- `create_draft(to, subject, body, thread_id=None)` — `users.drafts.create`
- `send_draft(draft_id)` — `users.drafts.send`
- `get_draft(draft_id)` — `users.drafts.get`

Gmail scope is already in the OAuth consent (`gmail.modify`) and in `google_oauth.py` SCOPES.

### 1b. Wire email tools (`tools/email_tools.py`)
Replace all 9 stub functions to call `gmail_provider.py`. The `_credentials(tool_context)` helper already exists and works — same pattern as docs/drive tools.

### 1c. Email tracking persistence (`Firestore`)
`email_track` and `email_get_tracking` currently return fake data. Need a `email_tracking` Firestore collection to actually persist which messages are awaiting reply and their deadlines.

### 1d. Email frontend page
Components already exist (`EmailInbox`, `EmailDraftCard`, `ExecutiveDigest`, `EmailThread`, `EmailTrackingPanel`) and are well-built UI shells. The sidebar link `/email` resolves to a 404 because there is no `app/[locale]/email/page.tsx`. Need to:
- Create the email route page
- Wire the components to the real API (they all contain hardcoded fake data)
- Wire `EmailDraftCard` approve/discard buttons to `POST /api/tasks/{id}/approve`

---

## Gap 2 — HITL (Human-in-the-Loop) Execution (P0 — System Broken)

**Current state:** `approval_create`, `slides_update`, and `slides_add_image` all create Firestore tasks with `status: "pending"`. `routers/tasks.py` has `approve_task` and `reject_task` endpoints that flip the status in Firestore. But there is no mechanism to resume the ADK runner after approval — the comment in `tasks.py` literally says `# runner.resume_task(task_id, "approved") — TODO`. The agent is permanently stuck after approval. This makes the `EditingAgent` (for doc edits) and `VisualAgent` (for slides content) **non-functional**.

**What needs to be built:**

### 2a. ADK runner resume wiring
The ADK `Runner` supports resuming a paused agent run. The pattern:
1. When agent calls `approval_create`, store the `tool_context` or session ID alongside the Firestore task
2. In `approve_task`, look up the session and signal the runner to resume with the approval result
3. The agent then proceeds to execute the actual write

### 2b. ApprovalCard integration in ChatWindow
`ApprovalCard` component exists and is well-built but is **never rendered anywhere** — it's an orphaned component. The ChatWindow needs to:
- Poll `GET /api/tasks` (or receive via SSE) for pending approval tasks
- Render `<ApprovalCard>` inline in the conversation when tasks are pending
- Call `POST /api/tasks/{id}/approve` or `/reject` when the user acts

### 2c. Slides write operations (unblock VisualAgent)
`slides_update` and `slides_add_image` go through the HITL queue and never execute. Once HITL is wired:
- `slides_update` should call `SlidesService.create_slide(presentation_id, title, subtitle)` after approval
- `slides_add_image` should actually insert an image into the slide after approval
- `SlidesService` needs methods to add text content to existing slides (currently only `create_presentation` and `create_slide` exist)

---

## Gap 3 — Knowledge Base / RAG (P0 — Core Feature)

**Current state:** All 5 functions in `tools/kb_tools.py` return hardcoded mock data (`kb_search` returns empty array, `kb_get_person` returns "John Doe", etc.). `tools/rag_tools.py` (`rag_retrieve`, `context_inject`) also return empty success responses. Config has `KB_RAG_CORPUS_ID`, `KB_GCS_BUCKET`, and `KB_INDEX_ENDPOINT` fields defined but nothing connects to them.

**What needs to be built:**

### 3a. RAG Engine / Vertex AI Search connection
Choose one approach:
- **Vertex AI RAG Engine** (`USE_RAG_ENGINE=true`): Use `google.adk.tools.vertex_ai_search_tool` or Vertex AI RAG API. Documents uploaded to GCS bucket `keralty-kb-documents` get indexed automatically.
- **Vertex AI Search (Discovery Engine)**: Create a datastore, index KB documents, use the search API.

Wire `rag_retrieve` in `tools/rag_tools.py` to call the chosen search API with the user's query and return ranked document chunks with citations.

### 3b. KB tools implementation (`tools/kb_tools.py`)
`kb_search` should call the RAG/search API with semantic search.
`kb_get_person`, `kb_get_department`, `kb_get_org_chart`, `kb_get_policy` can be either:
- RAG queries with structured prompt templates, OR
- A dedicated Firestore collection (`kb_people`, `kb_departments`, `kb_policies`) populated from org chart exports

### 3c. KB document ingestion pipeline
`routers/knowledge.py` has `POST /knowledge/documents` (admin-only) but it's a stub. Need real logic to:
1. Accept document upload (PDF, DOCX, Google Doc ID)
2. Process with Document AI or direct text extraction
3. Chunk and embed
4. Index in RAG Engine / Vector DB
5. Store metadata in Firestore `kb_documents` collection

### 3d. Admin panel KB management UI
`app/[locale]/admin/page.tsx` has a "Base de Conocimiento" section showing "Cargando documentos..." but fetches nothing. Wire it to `GET /knowledge/documents` and add upload functionality.

---

## Gap 4 — Voice Interaction (P1 — Advertised Feature)

**Current state:** `VoiceChat.tsx` connects to WebSocket `ws://backend/voice/stream`. The backend `routers/voice.py` accepts the connection and sends `{"type": "status", "message": "listening"}` in a loop — no audio is processed, no transcript is generated, no response audio is returned. The VoiceChat component is also **not mounted anywhere in the ChatWindow** — even the mock doesn't appear in the UI.

**What needs to be built:**

### 4a. Backend voice pipeline (choose one)

**Option A — Gemini Live API (native, no LiveKit)**
Config already has `GEMINI_LIVE_MODEL = "gemini-live-2.5-flash-native-audio"`. The Gemini Live API supports audio input/output over WebSocket. The flow:
1. Browser captures audio via `MediaRecorder` → sends PCM chunks to backend WebSocket
2. Backend pipes chunks to Gemini Live API session
3. Gemini returns text transcript + audio response chunks
4. Backend forwards audio chunks back to browser for playback via `AudioContext`

**Option B — LiveKit (if `USE_LIVEKIT=true`)**
Config has `USE_LIVEKIT` flag. LiveKit is a WebRTC SFU. The pipeline would be:
1. Create a LiveKit room on connection
2. Use LiveKit's Python SDK + Gemini plugin
3. Frontend uses LiveKit browser SDK for audio in/out

Option A is simpler given current setup.

### 4b. Frontend audio pipeline (`VoiceChat.tsx`)
The component needs:
- `MediaRecorder` setup to capture microphone audio
- Send audio chunks (PCM/16kHz) to backend WebSocket
- Receive response audio chunks and play via `AudioContext`
- Display transcript inline in ChatWindow

### 4c. Mount VoiceChat in ChatWindow
The `VoiceChat` component exists but is never imported or mounted. Add a microphone button alongside the text input in `ChatWindow.tsx`.

---

## Gap 5 — Session Persistence & Conversation History (P1)

**Current state:** `agents/runner.py` uses `InMemorySessionService`. Every time the Cloud Run instance restarts (which happens frequently with scale-to-zero), all conversation context is lost. `routers/history.py` returns empty arrays for all endpoints. The `History` page in the frontend shows "Cargando historial..." indefinitely. Firestore has `sessions` and `messages` collections defined in `FirestoreService` (with working `create_session`, `add_message`, `get_messages` methods) but they are **never called**.

**What needs to be built:**

### 5a. Switch to Firestore session service
ADK supports custom session services. Create `services/adk_session_service.py` that implements the ADK `BaseSessionService` interface, backed by Firestore. The session state (including `google_credentials`) must persist across requests.

### 5b. Message persistence in chat router
In `routers/chat.py`, after each user message and each agent response, call `FirestoreService.add_message()` to persist the exchange.

### 5c. History page implementation
Wire `app/[locale]/history/page.tsx` to call `GET /history/` (which should call `FirestoreService.get_sessions_by_user()`) and display past conversations with timestamps and message counts. Allow clicking to resume a session.

---

## Gap 6 — Image Generation — Imagen 3 (P1)

**Current state:** `tools/image_tools.py` has one function `image_generate(prompt)` that returns `{"image_url": "https://example.com/image.jpg"}` — a hardcoded fake URL. Config has `IMAGEN_MODEL = "imagen-3.0-generate-001"` defined. The VisualAgent calls this tool to generate images for presentation slides.

**What needs to be built:**

### 6a. Vertex AI Imagen 3 call
Replace the stub with a real Vertex AI call:
```python
from google.cloud import aiplatform
# or use vertexai.preview.vision_models.ImageGenerationModel
model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
images = model.generate_images(prompt=prompt, number_of_images=1)
```
Upload the result to GCS bucket and return a signed URL (or public URL if the bucket is public).

---

## Gap 7 — Document Context Injection into Chat (P1 — UX Gap)

**Current state:** `DocumentPicker` is a well-built component that calls `GET /documents` and displays Drive files with search. But it is **never imported or used anywhere** in the chat UI. Users have no way to attach a Drive document to a conversation so the agents can analyze it. The orchestrator's guardrail explicitly says "NEVER access documents the user hasn't selected in this session" — but there's no mechanism to select documents.

**What needs to be built:**

### 7a. Attach button in ChatWindow
Add a paperclip/attachment button to the chat input area that opens `DocumentPicker`.

### 7b. Session context injection on document select
When a user picks a document, call `DriveService.read_document_text(file_id)` and inject the content into the ADK session state (`session.state["attached_documents"]`). Update `AnalysisAgent` instruction to look for documents in session state.

### 7c. AnalysisAgent context_inject wiring
`tools/rag_tools.py` `context_inject` currently ignores the `context_id` and returns `{"status": "success", "injected": True}` without doing anything. It should actually inject the referenced context object into the agent's working memory or return it so the agent can use it.

---

## Gap 8 — ResearchAgent Drive Search (P2 — Incorrect Stubs)

**Current state:** `agents/research_agent.py` defines two **inline stub functions** (`drive_list_files` and `drive_search`) that return empty arrays — these shadow the real `drive_tools.py` functions. The agent gets the real `drive_read` tool (can read a specific file by ID) but cannot search Drive to find files.

**What needs to be built:**

Remove the inline stubs and import the real `drive_search` from `tools/drive_tools.py` (which calls `DriveService.list_documents`). The real function already supports a `query` parameter and uses the user's credentials.

---

## Gap 9 — OAuth Token Refresh (P0 — Silent Failure)

**Current state:** Google OAuth access tokens expire after 1 hour. `credentials_from_dict()` reconstructs a `google.oauth2.credentials.Credentials` object from the stored dict but does **not** attach a `requests.Request` object for auto-refresh. When the access token expires, all Workspace API calls will silently fail with 401 errors.

**What needs to be built:**

In `credentials_from_dict` (or wherever credentials are used), attach a `google.auth.transport.requests.Request()` to enable auto-refresh:
```python
from google.auth.transport.requests import Request
creds = Credentials(token=..., refresh_token=..., ...)
# Before using:
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    # Re-persist the refreshed token to Firestore
    FirestoreService.store_user_credentials(user_id, {}, credentials_to_dict(creds))
```
This should happen in `tools/_auth.py` `_credentials()` or in `routers/chat.py` before injecting into session state.

---

## Gap 10 — Sidebar Navigation Broken (P2 — UX)

**Current state:** The sidebar links to `/chat`, `/email`, `/history`, `/admin`. With `next-intl`, these resolve as `/es/chat`, `/es/email`, etc. The `/es/` page is the main chat. `/es/chat` is a 404 (doesn't exist). `/es/email` is a 404. `/es/history` and `/es/admin` exist as pages but show static "Cargando..." placeholders.

**What needs to be built:**
- Update sidebar `/chat` link to point to `/` or `/es` (the actual chat page)
- Create `app/[locale]/email/page.tsx` using the existing email components
- Wire `/history` and `/admin` pages to real backend data

---

## Gap 11 — Admin Panel (P2)

**Current state:** `app/[locale]/admin/page.tsx` renders three sections (Gestión de Usuarios, Métricas de Uso, Base de Conocimiento) but all show "Cargando...". Backend `routers/admin.py` has the route structure but all return empty arrays. `ADMIN_PANEL_ENABLED=true` is set in the Cloud Run frontend env.

**What needs to be built:**
- `GET /admin/users` → `FirestoreService.list_users()` (method needs to be added)
- `GET /admin/metrics` → aggregate from Firestore (session count, message count, costs from Vertex AI billing)
- KB document management UI wired to `GET/POST/DELETE /knowledge/documents`
- Audit log viewer wired to `GET /admin/audit` → `FirestoreService` audit_events collection

---

## Gap 12 — Audit Logging (P2)

**Current state:** `FirestoreService.log_audit_event()` exists and is fully implemented, and `AuditEvent` schema is defined in `models/schemas.py`. But `log_audit_event` is **never called anywhere** in the codebase. No Workspace action, no login, no approval is being logged.

**What needs to be built:**
Call `log_audit_event` at these points:
- User login (auth callback)
- Every docs_create / docs_update call
- Every email_send call
- Every slides_create call
- Every HITL approval/rejection

---

## Summary Table — Prioritized Work

| # | Feature | Files Affected | Priority | Effort |
|---|---|---|---|---|
| 1 | Gmail API integration (email tools + provider) | `services/email/gmail_provider.py`, `tools/email_tools.py` | P0 | Large |
| 2 | OAuth token auto-refresh | `tools/_auth.py`, `routers/chat.py` | P0 | Small |
| 3 | HITL execution (ADK runner resume) | `routers/tasks.py`, `agents/runner.py` | P0 | Medium |
| 4 | ApprovalCard in ChatWindow | `frontend/components/chat/ChatWindow.tsx`, `ApprovalCard.tsx` | P0 | Medium |
| 5 | RAG / Vertex AI Search for KB | `tools/rag_tools.py`, `tools/kb_tools.py`, new `services/rag.py` | P0 | Large |
| 6 | Session persistence (Firestore session service) | `services/adk_session_service.py`, `agents/runner.py`, `routers/chat.py` | P1 | Medium |
| 7 | Voice — Gemini Live API pipeline | `routers/voice.py`, `frontend/components/chat/VoiceChat.tsx`, `ChatWindow.tsx` | P1 | Large |
| 8 | Imagen 3 image generation | `tools/image_tools.py` | P1 | Small |
| 9 | DocumentPicker in ChatWindow | `ChatWindow.tsx`, `tools/rag_tools.py` (context_inject) | P1 | Medium |
| 10 | ResearchAgent Drive search fix | `agents/research_agent.py` | P1 | Small |
| 11 | Slides content writing (unblock VisualAgent) | `tools/slides_tools.py`, `services/slides.py` | P1 | Medium |
| 12 | Email frontend page | `app/[locale]/email/page.tsx`, email components | P2 | Medium |
| 13 | Conversation history page | `routers/history.py`, `services/firestore.py`, `app/[locale]/history/page.tsx` | P2 | Small |
| 14 | KB document ingestion pipeline | `routers/knowledge.py`, GCS + RAG Engine | P2 | Large |
| 15 | Admin panel functionality | `routers/admin.py`, `app/[locale]/admin/page.tsx` | P2 | Medium |
| 16 | Sidebar navigation fixes | `frontend/components/layout/Sidebar.tsx` | P2 | Small |
| 17 | Audit logging | All write tool files, `routers/auth.py` | P3 | Small |
| 18 | Observability (OTEL tracing) | `OTEL_ENABLED=true` in Cloud Run | P3 | Small |
| 19 | Microsoft Outlook support | New `services/email/outlook_provider.py` | P3 | Large |
| 20 | IAP authentication | `backend/auth/iap.py` | P3 | Medium |

---

## Architecture Notes for Implementation

**Email** — The OAuth token in Firestore already includes the `gmail.modify` scope. `_credentials(tool_context)` already works. Email tools just need to call Gmail API methods exactly as drive/docs tools do.

**RAG** — Vertex AI RAG Engine is the fastest path given the GCP setup. `vertexai.preview.rag` Python SDK. One GCS bucket upload triggers auto-indexing. `rag.retrieval_query()` replaces the stub in `rag_retrieve`.

**Voice** — Gemini Live API uses a bidirectional streaming WebSocket. The backend acts as a proxy: browser audio PCM → backend → Gemini Live → backend → browser audio output. Session is maintained server-side. No LiveKit required for single-user sessions.

**HITL resume** — ADK `InMemorySessionService` holds sessions in memory. The simplest approach: store `(session_id, user_id, tool_call_id)` in the Firestore task. On approval, the backend can re-inject the result into the session and trigger the agent to continue. This changes once we move to a real session service.

**Token refresh** — Should be handled in `tools/_auth.py` `_credentials()`: reconstruct creds, check `creds.expired`, call `creds.refresh(google.auth.transport.requests.Request())`, then re-persist to Firestore. Transparent to all tool callers.
