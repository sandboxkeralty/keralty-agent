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

# Test chat endpoint — requires a REAL JWT. There is no test-token bypass anymore:
# any invalid/expired token gets a hard 401 (a forged token used to authenticate
# as the sandbox user, which holds live Drive + Gmail credentials — that hole is
# closed). Log in via the OAuth flow (/auth/login) to obtain a token, or mint one
# locally with SECRET_KEY. A missing/invalid token → 401.
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <real-jwt>" \
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
            ├─ VisualAgent       (gemini-2.5-flash) — Google Slides + Imagen 3 (HITL)
            ├─ EmailAgent        (gemini-2.5-flash) — Gmail read/draft/send (HITL)
            └─ KnowledgeAgent    (gemini-2.5-flash) — corporate KB via hybrid RAG
```

All agents live in `backend/agents/`. The orchestrator's `INSTRUCTION` block in `orchestrator.py` contains the routing rules — **edit this when adding capabilities or fixing misdirected requests**.

**Model tiers are deliberate**: only AnalysisAgent and WritingAgent run `gemini-2.5-pro` (multi-document reasoning and long-form executive drafting, where Flash visibly degrades). VisualAgent and EmailAgent were downgraded to Flash in July 2026 — their outputs (slide outlines, short email drafts) don't need Pro, and Pro was the model hitting Vertex quota (429) daily. Don't bump an agent back to Pro without checking the quota picture first.

**Vertex 429 (`RESOURCE_EXHAUSTED`) defense — four stacked layers, all real and load-bearing:**
1. The backend Cloud Run service sets `GOOGLE_CLOUD_LOCATION=global`, which routes **only ADK agent traffic** to Vertex's global endpoint (capacity from any region) instead of competing for `us-central1`'s dynamic shared quota. The split works because ADK builds its Gemini client from env vars (google-genai reads `GOOGLE_CLOUD_LOCATION`), while `services/genai_client.py::get_genai_client()` passes an explicit `location=settings.GOOGLE_CLOUD_REGION` (`us-central1`) that overrides the env var — so voice (Live API), TTS, RAG rewrite/rerank, and email services stay region-pinned. **Keep it that way**: the Live model and preview TTS model are not safely assumed to exist on the global endpoint; chat + TTS + voice were all retested live after this change.
2. `routers/chat.py` retries a quota-failed turn up to 3 total attempts (2s/4s backoff) — but only while nothing has streamed yet, to avoid duplicated output. A retried turn re-appends the user message to the ADK session (accepted tradeoff).
3. Quota errors that survive retries stream a distinct `rate_limited` SSE event → frontend shows an honest "high demand, retry in a few seconds" message (`chat.errorRateLimited`) instead of the generic error.
4. Fewer Pro calls overall (see model tiers above).
There is **no per-project quota knob to raise** — Gemini 2.5 on Vertex uses dynamic shared quota (429s are capacity, not a limit you can file a ticket against); the paid escape hatch is Provisioned Throughput. Note the project's AI Studio Tier 1 API key (in the local `.env`) is **not** used in production — Cloud Run has `GOOGLE_GENAI_USE_VERTEXAI=1` and no `GOOGLE_API_KEY`, deliberately.

**Important ADK constraint**: Gemini's API rejects an agent whose `tools=[...]` list mixes the built-in `google_search` grounding tool with custom Python function tools ("Multiple tools are supported only when they are all search tools"). `ResearchAgent` needs both web search and custom Drive tools, so `google_search` is isolated inside its own single-tool sub-agent (`_web_search_agent` / `WebSearchAgent`, defined inline in `research_agent.py`) and exposed to `ResearchAgent` via `google.adk.tools.agent_tool.AgentTool` — never add `google_search` directly to any agent's `tools=[...]` alongside other tools; wrap it the same way instead.

**Routing is sticky across turns — this drives two prompt-level rules that must be preserved.** ADK's `Runner` routes each new user message to whichever agent authored the *last* event in the session (`_find_agent_to_run`), not back through `OrchestratorAgent` first. Confirmed by reading the installed `google-adk` source: every agent in the hierarchy gets an auto-injected `transfer_to_agent` tool (since none of the 9 `Agent(...)` constructors set `disallow_transfer_to_parent`/`disallow_transfer_to_peers`), so the mechanism to hand control back exists — but nothing forces an agent to use it. Two consequences baked into every agent's `INSTRUCTION` as a result:
1. Every sub-agent has a `# LÍMITES Y TRANSFERENCIA DE ALCANCE` block instructing it to call `transfer_to_agent(agent_name="OrchestratorAgent")` when a request falls outside its own listed tasks, instead of refusing outright. Without this, once e.g. `EditingAgent` becomes "active," an unrelated later request (e.g. "create a new spreadsheet") goes straight back to `EditingAgent` and it will incorrectly claim it can't do it — a real, previously-shipped bug. Each block also carries an explicit exception for continuations of the *current* flow (`[APROBADO] task_id=...`, a follow-up tweak to content the agent itself just proposed) so the transfer rule doesn't fire mid-approval-flow.
2. `OrchestratorAgent`'s own instruction explicitly forbids asking the user for permission before delegating ("¿Te parece bien si uso el ResearchAgent...?") — it must announce the plan in one sentence and proceed immediately. This is pure prompt wording, not an ADK behavior; ADK's own auto-injected transfer instructions already tell agents to call the tool directly without asking, so any permission-seeking is the model over-hedging on ambiguous instruction text, not a platform constraint.

Sticky routing means the *same* duplication is required for any instruction that must hold regardless of which agent ends up generating the reply. `# DOCUMENTOS ADJUNTOS EN EL CHAT` (see the "Attaching documents in chat" section below) is the second real case of this: every one of the 9 agents carries an identical block telling it that a `[Documento adjunto]` marker in the user's message is real, ready-to-use content — not a cue to search Drive/KB for it or ask the user to re-attach it. This was added after live testing showed attaching a document only worked correctly ~2 of 3 tries: whichever agent Gemini's routing happened to hand the turn to either inferred the marker's meaning correctly or didn't, since nothing had ever told it what that marker meant.

If you add a 9th sub-agent, give it both the `# LÍMITES Y TRANSFERENCIA DE ALCANCE` block and the `# DOCUMENTOS ADJUNTOS EN EL CHAT` block (see any existing agent file for the exact wording) — neither is optional boilerplate; both exist specifically because any agent can end up handling any turn.

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
- `backend/auth/auth_middleware.py` — JWT verification. **Any missing/invalid/expired token on an authenticated path returns a hard 401** — there is no `sandbox-user`/`test-token` fallback (that fallback was a security hole: a forged `Bearer` header authenticated as the sandbox user, which has real Drive + `gmail.modify` OAuth creds). Only authenticates paths matching `_AUTHENTICATED_PREFIXES = ("/api/", "/admin", "/knowledge", "/history", "/documents")` — **the `/voice` WebSocket route is deliberately excluded** (see `routers/voice.py`; WebSocket auth would need a different mechanism than the header-based check here). **Middleware registration order in `main.py` matters**: the auth middleware must be added *before* `CORSMiddleware` (Starlette wraps in reverse order, so last-added is outermost). With the order flipped, auth's short-circuited 401 `JSONResponse` never passes through CORS, leaves the server without `Access-Control-Allow-Origin`, and the browser reports an opaque "Failed to fetch" instead of a 401 — so the frontend's 401→login redirect never fires and an expired token bricks every page (this shipped broken and was found live; preflights passed, only the actual responses lacked headers).
- `backend/routers/auth.py` — `/auth/login` and `/auth/callback`
- `backend/routers/chat.py` — loads Firestore creds, injects into ADK session state; also persists messages
- `backend/tools/_auth.py` — `_credentials(tool_context)` helper: extracts creds, refreshes if expired, re-persists to Firestore (via `FirestoreService.update_credentials`, which touches only `google_credentials` — **not** `store_user_credentials`, which would null the profile on every refresh)
- `frontend/lib/api.ts` — the single frontend API client (base URL + bearer token + centralized 401→login handling). All fetch sites go through `apiFetch`/`apiJson`; **there is no `|| 'test-token'` fallback anymore** — a missing/expired token drops to the login gate.
- `frontend/components/layout/AuthGate.tsx` — captures the OAuth `?token=` redirect and gates the whole app: renders a "sign-in required" screen when unauthenticated or on any 401, instead of silently running as a guest.
- `frontend/components/layout/Navbar.tsx` — decodes the token for the email display; shows login/logout

### Google Workspace API access

All four service factories (`services/drive.py`, `docs.py`, `sheets.py`, `slides.py`) accept an optional `credentials` parameter. Every authenticated request now carries a real user (the middleware 401s otherwise), so their OAuth tokens flow from Firestore → session state → `_credentials(tool_context)` → service call. The `google.auth.default()` (service-account ADC) branch remains only as a defensive fallback when a logged-in user simply has no stored `google_credentials` yet — it is no longer reachable via a `test-token` shortcut.

Required Cloud Run env vars: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `SECRET_KEY`.

**Token auto-refresh**: `tools/_auth.py` checks `creds.expired`, calls `creds.refresh(GRequest())`, and re-persists updated tokens to Firestore. No silent 401s.

**`routers/documents.py` now threads real user OAuth credentials**, same as every other REST router that needs Google API access. A private `_credentials_for_user(user_id)` (mirroring `routers/email.py`'s helper of the same name — Firestore load → `credentials_from_dict` → refresh-if-expired → re-persist) is called via `_creds_from_request(request)` in all three Drive routes. This used to be a known, tracked gap (the DocumentPicker in chat always returned "No documents found," since it silently fell back to ADC — the service account owns none of a real user's files) — fixed by moving three things together in one change: adding `/documents` to `_AUTHENTICATED_PREFIXES` above, wiring `credentials=` into every `DriveService` call in `documents.py`, and adding the missing `Authorization` header to `DocumentPicker.tsx`'s fetch (it was the only authenticated-looking call in the whole frontend that omitted it). All three had to land together — gating `/documents` behind auth without the frontend header fix would have turned "always empty" into "always 401."

### Google Sheets tools & Drive search

`services/sheets.py`'s `SheetsService` transparently handles **both** native Google Sheets and raw uploaded `.xlsx`/`.xls` files by mimeType-detecting the target file (`_is_raw_excel_file`) and, for raw Excel, parsing it via `openpyxl` (downloaded through Drive's `get_media`, not the Sheets API — which only understands native Sheets IDs) instead of erroring out:
- `create_spreadsheet(title)` — creates a native Sheet, returns `{spreadsheet_id, first_sheet_title}` (the real, locale-dependent default tab name — never assume `"Sheet1"`)
- `append_values(id, range, values)` — `values().append` with `INSERT_ROWS`; finds the next empty row automatically
- `share_spreadsheet(id, email)` — targeted per-user sharing (mirrors `DocsService.share_document`), not the old `anyone/writer` grant
- Values read from raw Excel cells are passed through `_json_safe()` — openpyxl returns native Python `datetime`/`date` objects for date-formatted cells (the Sheets API never does), which aren't JSON-serializable when ADK sends the tool result back to Gemini

`tools/sheets_tools.py`:
- `create_spreadsheet(title, data_json=None)` — writes initial data in the same call (never leaves a spreadsheet empty when data was given)
- `sheets_list_tabs(spreadsheet_id)` — lists real tab names/IDs; call this before `read_spreadsheet_range` for any spreadsheet found by search rather than created in-session
- `read_spreadsheet_range`, `update_spreadsheet_values`, `append_spreadsheet_values`

`services/drive.py`'s `list_documents` accepts a `mime_types` param (aliased via `_MIME_TYPE_ALIASES`, e.g. `"spreadsheet"` → both the native Google Sheets mimeType and both Excel mimeTypes) and defaults (`_DEFAULT_MIME_TYPES`) to Docs/Slides/Sheets/Excel **plus PDF, Word (`.docx`/`.doc`), plain text, CSV, and Markdown** — so both `drive_search` and the chat Drive picker (`GET /documents`) find real-world uploaded files, not just native Office formats. The mimeType clause is parenthesized in the built query (`(mimeType='X' or mimeType='Y') and name contains '...'`) — without the parens, operator precedence silently broadens the query whenever a name filter is combined with 2+ mimeTypes.

### HITL (Human-in-the-Loop) approval flow

EditingAgent, VisualAgent, and EmailAgent all use a conversational HITL pattern:

1. Agent proposes changes → calls `approval_create` → Firestore task with `status=pending`
2. `routers/chat.py` SSE stream includes a `pending_approval` event with `task_id`
3. `ChatWindow.tsx` polls `GET /api/tasks` every 5 seconds while idle; renders `<ApprovalCard>` for each pending task
4. User clicks Approve → frontend calls `POST /api/tasks/{id}/approve` (ownership-checked; rejects if already rejected) → flips the task to `status=approved` → auto-sends `"[APROBADO] task_id={id}"` chat message
5. Agent sees `[APROBADO] task_id=...` and calls the destructive tool, which **re-verifies approval in code**

**The approval gate is enforced server-side, not by prompt text.** `tools/_approval.py::_require_approval` is called by every destructive tool (`email_send`, `docs_update`, `update_spreadsheet_values`, `append_spreadsheet_values`) before it acts: it looks up an `approved`, **user-owned**, not-yet-`consumed` Firestore task for the exact resource (`document_id`/`draft_id`/`spreadsheet_id` that `approval_create` stored), then marks it `consumed` so one approval authorizes exactly one execution. This closes a real bypass — previously the guarantee was prompt-only, so the literal text `[APROBADO] task_id=...` (including inside a prompt-injected **attached document**) could trigger a buffered send/write. `WritingAgent` no longer holds `docs_update` at all (edits route to the gated `EditingAgent`); only `docs_create`/`create_spreadsheet` (new-file creation) remain ungated. `slides_create` is still prompt-gated only — its approval task has no `document_id` at creation time, so the code gate can't key on it (tracked in `docs/audit-2026-07-remediation.md`).

Guardrail in each agent instruction: **NUNCA ejecutes la acción destructiva sin [APROBADO]** — now backed by the code gate above rather than trusting the model.

`ApprovalCard.tsx`'s diff display and the pending-tasks container both have capped, independently-scrollable heights (`max-h-48`/`max-h-[50vh]` with `overflow-y-auto`) — a long `changes_summary` or several stacked pending tasks used to push the Approve/Reject buttons below the visible viewport in the app's fixed-height, non-page-scrolling layout, with no way to reach them short of browser zoom-out.

### Voice input (speech-to-text)

```
Browser mic (getUserMedia 16 kHz mono)
  → AudioContext → AudioWorkletNode (public/audio-processor.js)
    → Float32→Int16 PCM conversion
    → base64-encode → WebSocket ws://.../voice/stream
      → backend: routers/voice.py
        → Gemini Live API (gemini-live-2.5-flash-native-audio —
          the only GA Live model on Vertex AI; there is no separate
          "half-cascade"/TEXT-modality model on Vertex AI, only on the
          direct Gemini API — response_modalities=["AUDIO"] is mandatory)
        ← input_audio_transcription (the model's own spoken reply/audio
          is generated but never read or forwarded — this feature is
          speech-to-text input only, not a spoken conversation)
      → WebSocket → VoiceChat.tsx accumulates transcript
        → onTranscript callback → ChatWindow sets input + auto-submits form
          → normal /api/chat SSE turn through the full Orchestrator + agents
```

**Do not set `response_modalities=["TEXT"]` or guess at a different model name for this** — both were tried and both failed in production: `TEXT` modality is rejected outright by the native-audio model (`1007` error), and a guessed model name (`gemini-live-2.5-flash`, without `-native-audio`) doesn't exist in Vertex AI's publisher model catalog at all (`1008` "not found"). The correct mechanism is `input_audio_transcription=types.AudioTranscriptionConfig()` in `LiveConnectConfig`, read back via `message.server_content.input_transcription.text` (`.finished` signals the final chunk) — not `message.text`, which is the model's own generated text and doesn't exist under `AUDIO` modality.

Key files: `frontend/components/chat/VoiceChat.tsx`, `backend/routers/voice.py`.

### Text-to-speech (on-demand "read aloud" — not auto-played)

A voice-initiated turn used to auto-play the assistant's reply via the browser's native `window.speechSynthesis` API — this was removed. Two real problems drove the removal: (1) users didn't want unsolicited audio playback on every voice turn, they wanted a manual control, and (2) `speechSynthesis` voice quality depends entirely on the end user's OS/browser-installed voices, and in practice it would often read Spanish text with an American-English accent since there was no way to guarantee a real Spanish voice was installed.

Replacement: every finished assistant message (not just voice-initiated ones) gets a small speaker icon (`ChatWindow.tsx`, `playMessage`/`stopPlayback`, `playingMessageId` state) that on click calls `POST /api/tts` (`backend/routers/tts.py`) and plays the returned audio via a plain `Audio()`/blob URL — no Web Audio API decoding needed, since the backend wraps the raw PCM in a real WAV header before returning it. Only one message plays at a time; clicking the currently-playing message's icon stops it.

`routers/tts.py` calls Gemini's native TTS (`GEMINI_TTS_MODEL` = `gemini-2.5-flash-preview-tts` by default, `GEMINI_TTS_VOICE` = `Kore`) via `client.aio.models.generate_content(..., response_modalities=["AUDIO"], speech_config=SpeechConfig(voice_config=...))` — confirmed empirically against the real `keraltysandbox` project that **both** the Vertex AI path and the API-key path serve this model (Vertex support for `-preview-tts` models isn't documented, only verified by testing). Gemini's TTS is multilingual and auto-detects the input language from the text itself, so the same voice persona correctly pronounces Spanish and English — there's no "Spanish voice" to pick, unlike OS voices. Response audio is `audio/L16;codec=pcm;rate=24000` (confirmed via the real API response's `inline_data.mime_type`, not hardcoded — the endpoint parses the actual rate out of that field with a 24kHz fallback) which gets wrapped via stdlib `wave` into a proper `.wav` before the response leaves the backend.

`backend/services/genai_client.py` holds the shared `get_genai_client()` helper (Vertex-if-`GOOGLE_GENAI_USE_VERTEXAI=1`, else API-key-if-`GOOGLE_API_KEY`, else Vertex ADC fallback) — extracted from `routers/voice.py` so both the Live API (STT) and `routers/tts.py` use one client-selection implementation instead of two copies.

**Gemini 2.5 Flash's "thinking" tokens count against `max_output_tokens` — always set `thinking_config=types.ThinkingConfig(thinking_budget=0)` on short, direct calls (classification, drafting) unless you specifically want chain-of-thought reasoning.** Without it, a real call in this codebase came back with `finish_reason=MAX_TOKENS` and a 4-word truncated response — the model spent nearly the entire token budget on invisible reasoning before it could emit any visible text (confirmed via `response.candidates[0].finish_reason` and `usage_metadata.thoughts_token_count`). This bit both `services/email/followup_service.py` and `services/email/triage_service.py` (see Gmail/Email agent section below) and is a real risk for *any* new short-output Gemini call added to this codebase. The RAG pipeline's `_rewrite_queries`/`reranker.py` calls **were hit by exactly this and are now fixed** (July 2026): both were silently returning empty/truncated output in production (`json.loads` "Expecting value"), so query expansion and reranking had degraded to no-ops — both now set `thinking_config=ThinkingConfig(thinking_budget=0)` and route through the shared `get_genai_client()`. See `docs/audit-2026-07-remediation.md`.

### RAG / Knowledge Base pipeline

Full 6-stage hybrid RAG in `backend/services/rag/`:

1. **Multi-query expansion** (`pipeline.py`): Gemini generates 3 semantic query variants
2. **Hybrid retrieval** (`retriever.py`): BM25 sparse (rank-bm25) + Vertex AI text-embedding-005 dense cosine similarity, fused via Reciprocal Rank Fusion across all query variants
3. **Neighbor expansion**: pulls ±1 adjacent chunks for top-20 fused results
4. **Gemini reranker** (`reranker.py`): scores each passage 0.0–1.0; dynamic gap cutoff (stops when `prev−curr > 0.2` and `len ≥ 4`); recall preservation adds back high-RRF items if result < min_k
5. **Abstention gate** (`pipeline.py`): concept-recall check (keyword coverage of query terms in retrieved text); abstains with follow-up suggestions if coverage < 0.5
6. **Context assembly**: `(Document Name, p.N)` citation blocks; `RAGResult` dataclass with `should_abstain`, `context_text`, `citations`, `coverage`

**Citations are humanized, never the raw filename.** `_build_context` (`pipeline.py`) runs each chunk's `filename` through `_humanize_filename` (strips the extension, turns `_`/`-` into spaces, title-cases) before building the inline reference — `keralty_exhaustivo.md` → `Keralty Exhaustivo`, rendered as `(Keralty Exhaustivo, p.6)`. Earlier this was a literal `[[keralty_exhaustivo.md:p6]]` tag that `KnowledgeAgent` copied verbatim into its answer and the frontend has no renderer for, so it showed up raw in the chat UI. Deliberately not a `[1]`/`[2]` numbering scheme — `_build_context` runs fresh per tool call, so sequential numbers would collide whenever `KnowledgeAgent` makes more than one KB tool call in the same turn; the named-reference form is collision-free by construction. Each entry in `RAGResult.citations` / the tool's `citations` list carries both the raw `filename` (kept for audit/debugging) and the new `display_name` (what should be shown/cited). `KnowledgeAgent`'s `INSTRUCTION` (`agents/knowledge_agent.py`) explicitly tells it to quote the formatted reference as-is and never emit the raw filename or `[[...]]` syntax.

Chunking (`chunker.py`): structure-aware paragraph split → greedy merge (max 1000 tokens) → coalesce < 120 tokens → 15% overlap (applied **last**, after coalescing — not before) → neighbor links.

**Token-count correctness matters more than it looks here.** Both `_merge_into_chunks` and `_coalesce_small` measure the token estimate (`len(text) // 4`) of the actual *joined candidate string*, not a sum of pre-computed per-block estimates — summing individually-truncated per-block counts systematically undercounts a joined string's real length (floor-division drift + untracked join-separator characters), which let chunk sizes silently balloon far past `max_tokens` for fragmented documents (pypdf's extraction of tables/forms/multi-column PDFs produces many tiny "paragraphs"; clean Markdown rarely triggers this). `_coalesce_small` also caps merges so a run of tiny fragments can never combine into an unbounded chunk. If you touch this file, re-test with a pathological input (hundreds of single-word "paragraphs"), not just clean text — that's exactly what shipped broken originally.

Embeddings (`embedder.py`): Vertex AI `text-embedding-005`, `RETRIEVAL_DOCUMENT` task type for indexing, `RETRIEVAL_QUERY` for queries. Batches by both item count (`_MAX_BATCH_ITEMS=250`) and an estimated token budget (`_MAX_BATCH_TOKENS=10000`, conservative on purpose). **The character-based token estimate can't be trusted to predict Vertex's real per-request 20000-token limit** — real tokenization density varies by language/content (Spanish text overshot the estimate by ~50% in production). `_embed_batch` self-heals: on the actual "token count exceeded" 400 error, it splits the failing batch in half and retries recursively, so correctness doesn't depend on the estimate being accurate, only on the pre-batching being a reasonable first line of defense.

Storage (`store.py`): Firestore `kb_chunks` collection (embedding arrays as List[float]), `kb_documents` collection for metadata.

Ingestion (`ingestion.py`): accepts PDF (pypdf), DOCX (python-docx), CSV (csv.DictReader), TXT/MD. GCS upload of originals to `keralty-agent-dev-artifacts` under a `kb/{doc_id}/{filename}` prefix (via `settings.GCS_BUCKET` — there is no separate `KB_GCS_BUCKET` setting; that was removed after it turned out to reference a bucket that was never actually provisioned). Cache invalidated after every ingestion. Requires `python-multipart` (FastAPI form/file parsing) and `google-cloud-aiplatform` (provides the `vertexai` import used here and by `tools/image_tools.py`) — both must be in `requirements.txt`; their absence was masked for a long time because the code paths that need them were gated behind `ADMIN_PANEL_ENABLED=false`.

Ingestion endpoint: `POST /knowledge/documents` (50 MB limit, admin-gated). Management: `GET /knowledge/documents`, `DELETE /knowledge/documents/{doc_id}`.

**Generation guardrails E10–E16** (chain-of-verification, entity consistency, timeline checks, numeric tools) are **delegated to agent prompt instructions**, not implemented as code.

### Gmail / Email agent

`services/email/gmail_provider.py` — full implementation using `googleapiclient.discovery.build("gmail", "v1", ...)`:
- `list_threads` — label filter, metadata headers
- `get_thread` — recursive MIME parser, prefers text/plain
- `search_threads` — Gmail query syntax
- `create_draft` — with optional thread_id for replies
- `send_draft`, `get_draft`
- `get_message_headers(message_id, credentials)` — lightweight metadata-only fetch (Subject/To/From/threadId/snippet); powers both the tracking-record enrichment and the follow-up personalization below, so it's the one place that knows how to cheaply look up "what was this message about" without downloading the full body

`tools/email_tools.py` — all 9 functions call `GmailProvider` with `_credentials(tool_context)`. EmailAgent has mandatory HITL before `email_send`.

`email_track(message_id)` writes to Firestore `email_tracking` — and, as of this cycle, also calls `get_message_headers` to capture `subject`/`to` at tracking time, so the follow-up dashboard has real descriptive info to show instead of a bare Gmail `message_id` (that used to be the only thing stored, and the dashboard would literally render the raw ID as the item's title).

**`services/email/followup_service.py`** — `generate_followup_draft(tracking_id, credentials)` is the single shared implementation behind both `email_generate_followup` (the ADK tool, has a `tool_context`) and the REST endpoint below (has `request.state.user` instead) — the draft-creation logic doesn't otherwise differ between the two callers, so it lives here once. As of this cycle the follow-up body is generated by Gemini (`GEMINI_FLASH_MODEL`, `thinking_budget=0` — see Text-to-speech section above for why that matters) using the original message's subject/snippet, instead of a hardcoded template string; falls back to the old generic template if the LLM call fails for any reason. Returns `{draft_id, subject, to, body}` — the frontend shows the actual generated `subject`/`body` inline rather than a bare "created" message.

**`services/email/triage_service.py`** — `classify_priority(threads)` takes a list of thread dicts (`from`/`subject`/`snippet`, the same shape `search_threads` already returns) and returns one `CRITICO`/`ALTO`/`MEDIO`/`BAJO` label per thread via a single batched Gemini call (same "one prompt, N candidates, parse a same-length JSON array" pattern as `services/rag/reranker.py`), reusing the exact rubric `EmailAgent`'s own chat instruction already defines (board/regulator senders, deadline keywords, meeting requests, stale threads, newsletters). Falls back to `MEDIO` for every item on any failure — a triage outage never breaks the rest of the dashboard. This exists because the dashboard's "Críticos" tile used to just relay Gmail's generic `is:important` flag, which isn't the same thing as the agent's own priority judgment and doesn't showcase any actual AI reasoning.

**Email dashboard** (`GET /api/email/summary`, `routers/email.py`, mounted at `/api/email` so it's covered by the standard `/api/` auth check — no `auth_middleware` change needed for it): a plain REST endpoint, not an ADK tool, so it can't use `tool_context` — it has its own small `_credentials_for_user(user_id)` helper that mirrors `tools/_auth.py`'s load-refresh-repersist logic but is keyed directly off `request.state.user`. Returns `inbox_today` (deduped by `thread_id`, each item enriched with a `priority` field from `triage_service`), `tracked`, `indicators` (`bandeja`/`criticos`/`pendientes`/`seguimiento`), and `warnings` (a list of which sub-fetches failed, if any — added because every fetch used to fail silently into `0`/`[]`, making a real Gmail-token failure indistinguishable from a genuinely empty inbox; the frontend shows an inline banner when this is non-empty).

**Timezone handling — accepts a `tz` query param, an IANA name like `America/Bogota`.** `frontend/app/[locale]/email/page.tsx` sends `Intl.DateTimeFormat().resolvedOptions().timeZone` (the browser's live local timezone — wherever the executive is actually logged in from *right now*, not a fixed Keralty HQ zone) on every `fetchSummary()` call. The backend's `_local_midnight_epoch(tz)` computes local midnight via stdlib `zoneinfo.ZoneInfo` and converts to a Unix epoch second, then queries Gmail with `after:<epoch>` instead of a `YYYY/MM/DD` string. This matters: the old implementation computed "today" from `datetime.now(timezone.utc)` and handed Gmail a bare date string — for any executive west of UTC (all of Keralty's actual LatAm operating countries), UTC rolls over to the next calendar day several hours before local midnight, so mail received in the evening would silently vanish from **Bandeja**/**Críticos**/**Pendientes** for that whole window. Gmail's `after:`/`before:` operators accepting raw epoch seconds is not prominently documented — confirmed empirically (a query with a deliberately-future epoch correctly returned zero results) rather than assumed. `tz` falls back to UTC if missing or invalid (`ZoneInfoNotFoundError` is caught).

`POST /api/email/tracking/{tracking_id}/generate-followup` — the dashboard's "Generar seguimiento" button used to be a literal no-op (`onClick={() => {}}`); this endpoint wraps `followup_service.generate_followup_draft` for REST callers. Draft-only, same as `email_draft` — no HITL gate needed since nothing is sent, matching the tool's existing security model.

`frontend/app/[locale]/email/page.tsx` calls `GET /api/email/summary?tz=...` on mount and on the "Actualizar" button.

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

`tools/image_tools.py` — calls `vertexai.preview.vision_models.ImageGenerationModel` with `IMAGEN_MODEL` (default `imagen-3.0-generate-001`). Uploads result bytes to GCS `keralty-agent-dev-artifacts/images/`, makes blob public (`blob.make_public()`), returns public URL. Falls back to placeholder URL on any error — this silently masked both a missing bucket and a missing `google-cloud-aiplatform` dependency for a long time; if image generation ever silently starts returning placeholders again, check those two things first before assuming a prompt/model issue.

The bucket has **uniform bucket-level access disabled** specifically so `make_public()`'s legacy per-object ACL call keeps working — the bucket also holds private KB documents (`kb/` prefix) alongside public images (`images/` prefix), so making the whole bucket public via IAM instead (the usual fix for UBLA + public objects) would wrongly expose KB content. Only `image_tools.py` calls `make_public()`; KB uploads in `ingestion.py` never do, so they stay private by default. The Cloud Run backend's service account (`keralty-agent-sa@...`) has `roles/storage.objectAdmin` scoped to this one bucket, not a project-wide storage role.

### Session persistence & history

`backend/services/adk_session_service.py` (FirestoreSessionService) — ADK `BaseSessionService` backed by Firestore `adk_sessions` collection. **Both state AND events survive cold starts.** Events (the conversation history the model actually reads) were originally in-memory only, on the assumption that the `messages` collection covered history — but `messages` only feeds the history sidebar and is never fed back to the model, so every cold start, **redeploy**, or scale-out to a second Cloud Run instance silently wiped the model's conversational memory mid-conversation (user-visible as "no tengo memoria de la instrucción anterior" right after an error or deploy). Events now persist to an `events` subcollection under each `adk_sessions` doc — one doc per event (`event_json` = the Pydantic-serialized ADK `Event`), so the parent doc's 1 MB limit is never in play — and are reloaded in timestamp order on restore. Three subtleties encoded there: (1) `_get_or_restore` compares the Firestore doc's `last_update_time` against the in-memory copy and reloads when Firestore is newer, so two concurrent Cloud Run instances don't serve each other stale history; (2) one undecodable event (ADK schema drift across upgrades) is skipped, not allowed to discard the whole history; (3) `delete_session` explicitly deletes the subcollection docs — Firestore does *not* cascade-delete subcollections, and orphaned events would resurrect into a reused session id.

`routers/chat.py` persists every user message and agent response to Firestore `messages` collection after each turn.

`routers/history.py`:
- `GET /history/` — all sessions for the authenticated user, with message count and 120-char preview
- `GET /history/{session_id}` — full message thread (ownership-checked)
- `DELETE /history/{session_id}` — deletes session (messages retained for audit)

**Frontend architecture (Claude.ai/ChatGPT-style, not a separate history page)**: there is no `/history` route in the frontend anymore — it was removed once the sidebar covered everything it did. `frontend/hooks/useChatSession.tsx` (`ChatSessionProvider`/`useChatSession`) holds `sessionId` and `messages` in React context, provided once at the `AppShell` level (`components/layout/AppShell.tsx`) so it persists across route navigation instead of living as local state inside `ChatWindow`. `components/layout/Sidebar.tsx` fetches `GET /history/`, groups sessions by recency (Hoy/Ayer/Últimos 7 días/Anteriores), and on click fetches `GET /history/{id}` and calls the context's `loadSession(id, messages)` — switching conversations updates the same mounted `ChatWindow` instantly, with no page reload. "Nueva conversación" calls `startNewConversation()`, which generates a fresh `session_id` — **`sessionStorage`'s `keralty_session` key persists per browser tab, so anything that doesn't explicitly call `startNewConversation()` will keep silently reusing the same session** (this was a real, shipped bug before the redesign: the old sidebar link just navigated to `/` without clearing it).

Composite Firestore indexes actually required (mismatches here silently 500 every request — the exception is swallowed by the frontend's `if (res.ok)` check, so a broken index looks identical to "no data" in the UI):
- `sessions(user_id ASC, updated_at DESC)` — **not** `created_at`; `get_sessions_by_user` orders by `updated_at`
- `messages(session_id ASC, timestamp ASC)` — **not** `created_at`; `get_messages` orders by `timestamp`, and `MessageInDB` doesn't even have a `created_at` field

### Admin panel

`frontend/app/[locale]/admin/page.tsx` — 5 tabs, all fetching live backend data:
- **Métricas**: 4 stat cards (sessions, messages, users, audit events) from `GET /admin/metrics`
- **Usuarios**: user table with avatar, role badge, last activity from `GET /admin/users`; `PATCH /admin/users/{email}` for name/role edits
- **Knowledge Base**: file upload → `POST /knowledge/documents`; indexed documents table with delete
- **Auditoría**: color-coded action badges from `GET /admin/audit`
- **Configuración**: feature flag badges from `GET /admin/configs` (read-only)

All admin endpoints gated on `ADMIN_PANEL_ENABLED=true` (this is the **only** gate — there is no per-user role check anywhere in the backend; `request.state.user` never carries a `role`, and Firestore `users.role` is an unenforced free-text field). Once the flag is on, every authenticated user gets full admin access. The deployed Cloud Run backend currently has this flag set to `true` via `--update-env-vars` (the code default in `config.py` is `false`) — check the live env var, not just the code default, before assuming the panel is inaccessible. See `docs/product-roadmap-new-features.md` (Tier 0.1) for the planned RBAC work.

### Attaching documents in chat (Drive + local upload)

Paperclip button in `ChatWindow.tsx` opens `<AttachMenu>` (`components/documents/AttachMenu.tsx`), a small two-row menu: "Upload from device" and "Google Drive." Both sources converge on the same `attachedDoc: { file: DriveFile; text: string } | null` state and the same chip UI — a locally uploaded file is wrapped in a synthetic `DriveFile`-shaped object (`id: "local:<timestamp>"`) so no downstream code needs to know which source it came from.

- **Google Drive**: selecting "Google Drive" opens the existing `<DocumentPicker>` modal; selected file text is fetched from `GET /documents/{file_id}/text`.
- **Local upload**: selecting "Upload from device" triggers a hidden `<input type="file">` (`accept=".pdf,.docx,.doc,.txt,.csv,.md"`), which posts to `POST /documents/upload` — a lightweight endpoint that runs the file through `services/rag/ingestion.py`'s `extract_text()` and returns `{filename, text}`. **Deliberately does not use `POST /knowledge/documents`** — that endpoint is admin-gated and permanently indexes into the org-wide Knowledge Base; a one-off chat attachment must not leak into that. 50 MB cap, same allowed types as KB ingestion (`pdf`, `docx`, `doc`, `txt`, `csv`, `md`), errors surface inline as `uploadError` (415 unsupported type, 413 oversized, 422 empty/unextractable).

Either way, the resulting text is sent as `attached_context` in the chat request body, along with `attached_file_id`/`attached_file_name`/`attached_mime_type`. For real Drive files, `routers/chat.py` renders the marker as `[Documento adjunto: <name>]` plus a `[drive_file_id: <id> | mimeType: <type>]` line so agents can operate on the *file itself* (edit the Sheet, extend the Doc/Slides via their tools) rather than only its extracted text — every agent's `# DOCUMENTOS ADJUNTOS` block explains this, and the orchestrator routes modification requests by type (EditingAgent for Docs/Sheets, VisualAgent for Slides). The `drive_file_id` line is **deliberately omitted for local uploads** (their synthetic `local:<ts>` id is filtered in `chat.py`): the file doesn't exist in Drive, and including an id would bait agents into Drive calls that must fail. `routers/chat.py` injects it directly into the `new_message` parts sent to `runner.run_async` (prefixed `[Documento adjunto]`), capped at 8000 chars — **this must be a message part, not just `session.state["attached_documents"]`**. An earlier version only wrote it to session state and never read it back out anywhere (no agent instruction or tool referenced that key), so attaching a document silently never reached the model at all, for either source — confirmed by testing the full round-trip, not assumed. `attachedDoc` is cleared after a successful send (fixed alongside this — it previously wasn't, so every subsequent turn re-appended the same text into session state, growing it unboundedly for the whole session).

Getting the text into the message wasn't sufficient on its own — see the sticky-routing note in the Agent pipeline section above. All 9 agents now carry a `# DOCUMENTOS ADJUNTOS EN EL CHAT` block explicitly telling them the `[Documento adjunto]` marker is real, already-available content to use directly, never something to re-fetch via a Drive/KB tool or ask the user to resend. Verified live, 5 for 5 correct answers after adding the block (vs. roughly 2 of 3 before it, with the failure mode being the agent claiming no file was attached despite the text being right there in its context).

**The Drive picker's `GET /documents` call must use the trailing-slash path (`/documents/?q=...`), not `/documents?q=...`.** FastAPI 307-redirects the latter to the former, and that redirect's `Location` header comes back as `http://` instead of `https://` — Cloud Run's load balancer terminates TLS and forwards plain HTTP to the container, and Uvicorn isn't told to trust `X-Forwarded-Proto`, so it builds the redirect from the scheme it actually saw (confirmed via `curl -i`, not assumed). A real browser on the `https://` frontend silently blocks that as mixed content; the request never completes, and `DocumentPicker.tsx`'s catch-all error handling made this look identical to a genuine empty result — "No documents found" either way. **`curl -L` does not reproduce this** (curl doesn't enforce mixed-content policy), which is why earlier curl-based verification of the credential-threading fix didn't catch it — this bit was only found by driving the real UI in a browser. `DocumentPicker.tsx` now calls the canonical `/documents/` path directly to skip the redirect entirely, rather than fixing proxy-header trust at the Uvicorn/infra level (smaller, more targeted diff for this specific call site).

**The Drive picker (and `drive_search`) can now find and read PDF, Word (`.docx`/`.doc`), plain text, CSV, and Markdown files, not just native Google Docs/Slides/Sheets and Excel.** `services/drive.py`'s `_DEFAULT_MIME_TYPES` was silently narrow — real files of those types existed in the sandbox Drive and simply never appeared in search results. `read_document_text` also could not have extracted their content even if found: it only ever handled native-Doc/Slide export and a Sheets-tabs stub, falling back to a bare `"Unsupported file type."` string for everything else. Fixed by adding a `_EXTRACTABLE_MIME_TO_FILETYPE` fallback in `read_document_text` that downloads the raw bytes via Drive's `get_media` (the same non-native-file pattern `services/sheets.py` already uses for raw `.xlsx`) and runs them through `services/rag/ingestion.py`'s `extract_text()` — the same extractor local chat uploads use. Verified against real files in the sandbox Drive (not synthetic test files): both a real PDF and a real `.docx` were previously invisible in search and are now found and correctly extracted.

**The "Select from Google Drive" panel had no way to close it except selecting a file** — no X button, no click-outside handling, no Escape key. `DocumentPicker` now takes an `onClose` prop (rendered as an X in its header) and `ChatWindow.tsx` wraps the paperclip button plus both the `AttachMenu` and `DocumentPicker` popovers in a `attachAreaRef`-tracked container with a document-level `mousedown`/`keydown` listener that closes whichever is open on an outside click or Escape.

### SSE streaming

`routers/chat.py` streams ADK events as `text/event-stream`. ADK `Part` objects always have a `.text` attribute (Pydantic field defaulting to `None`), so the guard must be `if p.text is not None:` — **not** `if hasattr(p, "text"):`.

**Live agent-status label** (the "Consultando la base de conocimiento…" line shown while the assistant works, instead of a bare blinking cursor): `routers/chat.py` reads `event.author` (agent name) and `event.get_function_calls()[0].name` (tool) off every ADK event and streams them as `{'type': 'status', 'agent': ..., 'tool': ...}` SSE events — deduped on the `(agent, tool)` pair so a multi-part turn doesn't spam identical events, and `author == "user"` events are skipped. `ChatWindow.tsx` holds the latest pair in `agentStatus` state (a single state, not per-message — only one reply streams at a time; reset on submit and in the `finally`) and resolves it to a localized label via `statusLabel()`: **tool mapping wins over agent mapping** (more specific), `transfer_to_agent` is deliberately ignored as a tool (falls through to the agent label), and anything unrecognized falls back to the pre-existing `chat.agentThinking` key. The 16 `chat.status*` keys (plus `chat.errorRateLimited`) live in both `frontend/messages/{es,en}.json`. Tool matching is prefix-based (`kb_`, `drive_`, `docs_`, `sheets_`/`spreadsheet`, `slides_`, `email_`) — a new tool following the existing naming conventions gets a sensible label for free; a new *agent* needs a `case` added in `statusLabel()` plus message keys, or it degrades gracefully to "thinking". The label row renders only while `isStreaming && !content`; once real text starts streaming it's replaced by the original cursor. Verified against the live deployment: a KB question streams `OrchestratorAgent` → `KnowledgeAgent`+`kb_search` → content.

Chat messages are rendered as Markdown in the frontend using `react-markdown` + `remark-gfm`, so agent responses with links, tables, headings and lists display correctly. `ChatWindow.tsx` passes a custom `a` renderer (`MarkdownLink`, alongside the existing `img: MarkdownImage`) so every link in an agent response — the Docs/Sheets/Slides URLs `docs_create`/`create_spreadsheet`/`slides_create` return, in particular — opens with `target="_blank" rel="noopener noreferrer"` instead of navigating the user away from the app in the same tab.

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
| No role-based access control | `auth/auth_middleware.py`, `routers/admin.py` | `ADMIN_PANEL_ENABLED` is a single global flag with no per-user role check; anyone gets full admin access once it's on, or none at all |
| Audit logging — slides & KB & local uploads | `tools/slides_tools.py`, `routers/knowledge.py`, `routers/documents.py` | `slides_create`, KB document ingestion, and `POST /documents/upload` are not logged to `audit_events`; all other write operations (docs, sheets, email, HITL) are |
| RAG generation guardrails E10–E16 | _(no code file)_ | Chain-of-verification, entity consistency, timeline/numeric checks delegated to agent prompt instructions, not implemented as callable tools |
| Outlook email provider | `backend/services/email/outlook_provider.py` | Empty stub — Azure OAuth vars defined in config but provider not implemented; there is also no Outlook-equivalent of `auth/google_oauth.py` yet, so this is a full OAuth-flow build, not just a provider |
| Email package scaffolding | `backend/services/email/{__init__,base,factory}.py` | All empty — only `gmail_provider.py` is implemented |
| Legacy email stub | `backend/services/email.py` | 49-line stub GmailProvider returning mocks — **not imported anywhere** (superseded by `services/email/gmail_provider.py`); safe to delete |
| Legacy service stubs | `backend/services/{knowledge_base,storage,voice}.py` | All empty, not imported anywhere — scaffolding left over from early design |
| Vertex AI utility | `backend/services/vertex_ai.py` | Minimal: `init_vertex_ai()` and `get_grounding_tool()` — called only if `USE_VERTEX_AI=true` / `SEARCH_GROUNDING_ENABLED=true`; `get_grounding_tool()` specifically is defined but never actually wired into any agent |
| No automated test suite | _(no `tests/` directory)_ | Only ad-hoc one-off scripts exist as precedent (e.g. historical `test_signature.py`); every fix this cycle was verified by manually exercising the live deployment |

See `docs/product-roadmap-new-features.md` (Tier 0) for the planned fixes to the RBAC, testing, and observability gaps above.

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
- **Firestore composite indexes** (deployed): `email_tracking(user_id,status)`, `tasks(user_id,status,created_at)`, `messages(session_id,timestamp)`, `sessions(user_id,updated_at)` — **double-check the actual field name a query orders by before assuming an index matches it.** Two of these were originally deployed against the wrong field (`created_at` instead of `timestamp`/`updated_at`), which silently 500'd conversation history for an unknown period — the frontend's `if (res.ok)` checks swallowed the error, so it just looked like "no data" in the UI, not a bug.
- **GCS bucket**: `keralty-agent-dev-artifacts` — stores generated images (`images/`) and KB original files (`kb/`). Uniform bucket-level access is **disabled** on this bucket (see Imagen 3 section for why). The Cloud Run backend's service account has `roles/storage.objectAdmin` scoped to this bucket specifically.
- **Active GCP account**: `sandboxkeralty@gmail.com`
- **GitHub repo**: `https://github.com/sandboxkeralty/keralty-agent.git` — push as user `sandboxkeralty` (`gh auth switch --user sandboxkeralty`)

Enabled APIs: Drive, Docs, Sheets, Slides, Gmail, Vertex AI, Gemini, Firestore, Cloud Run, Artifact Registry, Cloud Build, Logging, Monitoring, Trace. **Not enabled** (verified directly, despite being assumed in earlier planning docs): Calendar, Cloud Scheduler, Cloud DLP — all three are prerequisites for specific items in `docs/product-roadmap-new-features.md` and need enabling (plus, for Calendar, a new OAuth scope + user re-consent) before that work starts.

---

## i18n

Frontend uses `next-intl` with locales `en` and `es` (default `es`). Message files are at `frontend/messages/{en,es}.json`. The middleware at `frontend/middleware.ts` handles locale prefixing for all non-API routes.

`backend/i18n/` exists as a scaffold but all files are empty — backend responses are in the agent's natural language (Spanish/English bilingual per orchestrator instruction).

---

## Branding

`branding/` holds the source-of-truth brand assets — `Paleta de colores Keralty.xlsx` (official
Pantone-mapped hex palette), `Template_Keralty.pptx` (the executive presentation template; its
body font, Calibri, and its dominant navy, `#002060`, are what the frontend's brand colors and
typography are actually derived from — not the palette xlsx alone, which uses slightly different
navy shades), and `logo.png` (transparent PNG, dark navy wordmark — copied to
`frontend/public/keralty-logo.png` for actual use).

`frontend/app/globals.css`'s `@theme` block holds the applied brand colors
(`--color-primary: #00B288`, `--color-navy: #002060`, etc.) — **check this file's comments and
`branding/` before changing any brand color**, don't eyeball a replacement. The body font is
Carlito (`app/[locale]/layout.tsx`, loaded via `next/font/google`), a freely-licensed
metric-compatible match for Calibri — the CSS previously declared `font-family: 'Inter'` but
never actually loaded that font anywhere, so it silently fell back to `system-ui`; this is now
fixed and wired correctly.

The logo is displayed in the sidebar header on a **white badge**, not directly against the
sidebar's dark navy background — its wordmark is dark navy too, so it would be illegible without
the white backing.

---

## Related documentation

- `README.md` — project overview, architecture diagram (Mermaid), setup, and deployment quick
  reference
- `docs/product-roadmap-new-features.md` — forward-looking roadmap for the *next* development
  cycle (this file, `CLAUDE.md`, documents the system as it exists *today*)
- `docs/use-cases-strategic-testing.md` — end-to-end test scenarios for every feature, written
  from an executive user's perspective; run through this after any deployment that touches more
  than one component
- `docs/live-voice-architecture-proposal.md` — scoped-but-deferred proposal for a true real-time,
  low-latency voice conversation with full tool/agent access (not implemented; requires a
  product decision on how HITL approvals work in a spoken flow before it can be estimated)
