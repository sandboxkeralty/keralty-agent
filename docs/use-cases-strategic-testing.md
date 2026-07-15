# Keralty Assistant — Strategic Use Case Test Script

This document walks through every capability of Keralty Assistant as a **senior executive**
(CEO, country VP, or a member of their office) would actually use it — not as isolated feature
checks, but as the real strategic tasks that make up an executive's week at a 9-country
healthcare holding company. Use it to validate the platform end-to-end after any deployment, or
to onboard a new executive user to what the assistant can do for them.

## Before you start

- **Log in with a real Google account**, not the `test-token` fallback. Most scenarios below
  need genuine Drive/Sheets/Gmail access — the fallback sandbox identity only works reliably for
  Knowledge Base questions and generic conversation.
- Prompts below are written in Spanish, matching how the assistant is actually used inside
  Keralty — everything works identically in English.
- Each scenario states what it validates so a failure points you straight at the responsible
  component.

---

## 1. Morning Knowledge Base briefing

**Executive context:** Before a board call, the CEO wants a quick refresher on Keralty's
organisational structure and strategy without digging through SharePoint-style folders.

**Steps:**
1. *"¿Cuáles son las prioridades estratégicas de Keralty para este año?"*
2. *"¿Quién lidera la operación en Colombia?"*

**Expected result:** `KnowledgeAgent` answers with citations to the specific KB document/section
it drew from. If the KB has no relevant content, it says so explicitly rather than inventing an
answer.

**Validates:** hybrid RAG retrieval (BM25 + dense), Gemini reranking, the abstention gate.

---

## 2. Analyzing an internal strategy document

**Executive context:** The CEO has a Google Doc with last quarter's regional performance review
and wants an executive summary before a 1:1 with a country VP.

**Steps:**
1. *"Analiza el documento 'Revisión Q2 Colombia' y dame un resumen ejecutivo: puntos clave,
   conclusiones, riesgos y acciones recomendadas."*

**Expected result:** `AnalysisAgent` retrieves the document, produces the 5-part structured
summary (Propósito / Puntos clave / Conclusiones / Riesgos / Acciones), and cites the exact
source file for every claim.

**Validates:** `drive_read`, document-grounded analysis, citation discipline.

---

## 3. Building a data sheet from scratch

**Executive context:** The CEO needs a small tracking sheet for a pilot program — patient
demographic categories for a regulatory submission draft, before handing it to Legal.

**Steps:**
1. *"Crea una hoja de cálculo con 3 columnas: nombre, edad y sexo, y agrega una fila de datos
   de prueba."*

**Expected result:** `WritingAgent` creates a real Google Sheet with the data already populated
(never an empty sheet), returns a working link, and the file is shared to your own Drive — not
just the service account's.

**Validates:** `create_spreadsheet` with `data_json`, per-user sharing (not `anyone/writer`).

---

## 4. Finding and reading an existing spreadsheet (including uploaded Excel files)

**Executive context:** A colleague emailed the CEO an `.xlsx` budget file, already saved to
Drive, and the CEO doesn't remember the exact file name.

**Steps:**
1. *"Busca en Drive un archivo de hoja de cálculo relacionado con 'presupuesto' y analízalo."*
2. Once found: *"¿Qué pestañas tiene este archivo?"*
3. *"Léeme los datos de la pestaña [nombre real de la pestaña]."*

**Expected result:** `drive_search` finds the file even though it's a raw uploaded Excel file
(not a native Google Sheet), `sheets_list_tabs` reports the real tab names (never assumes
"Sheet1"), and the data reads back correctly — including any date-formatted cells.

**Validates:** Drive search across native + uploaded Office mimeTypes, `openpyxl`-based reading
of raw Excel files, JSON-safe serialization of date cells.

---

## 5. Updating an existing spreadsheet — with approval

**Executive context:** The CEO wants to add this month's numbers to an existing tracking sheet
without accidentally overwriting historical data.

**Steps:**
1. *"Agrega una fila a la hoja 'Presupuesto 2026' con los datos: Julio, Marketing, 12000."*
2. Review the proposed change shown in the approval card.
3. Click **Aprobar**.

**Expected result:** Nothing is written until you approve. After approval, the new row is
appended after existing data (never overwritten), confirmed with the updated range.

**Validates:** `EditingAgent`'s HITL flow, `append_spreadsheet_values`, the
`[APROBADO] task_id=...` gate.

---

## 6. Drafting a board communication (Google Doc)

**Steps:**
1. *"Redacta un memo ejecutivo sobre el desempeño de Colombia en Q2, con audiencia ejecutiva,
   y guárdalo como Google Doc."*

**Expected result:** `WritingAgent` drafts full Markdown content, creates the Doc with that
content already written in (never empty), and returns the link.

**Validates:** `docs_create` with `content`, `ReviewAgent` handoff for quality.

---

## 7. Editing an existing document — with approval

**Steps:**
1. *"Actualiza el documento 'Memo Colombia Q2' añadiendo una sección sobre el riesgo
   regulatorio de COFEPRIS."*
2. Approve the proposed diff.

**Expected result:** The current content is fetched first, the proposed addition is shown in
plain language (not raw diff syntax), and it's only written after approval.

**Validates:** `EditingAgent`, `docs_get` → `docs_update`, approval gate.

---

## 8. Building a board presentation with a generated image

**Executive context:** The CEO needs a short deck for a stakeholder update, including a
professional cover visual.

**Steps:**
1. *"Prepárame una presentación de bienvenida para el equipo de Keralty, 3 slides."*
2. Approve the proposed outline.
3. *"Genera una imagen corporativa para la portada."*
4. Hover the generated image in chat and click the download icon.

**Expected result:** The outline is approved before creation; `slides_create` builds the real
presentation in one call; `image_generate` produces a real Imagen 3 image (not a placeholder);
the download button saves an actual file, not just opening the image in a new tab.

**Validates:** `VisualAgent`'s HITL flow, GCS bucket + IAM for image storage, the
`MarkdownImage` download component with cache-busting fetch.

---

## 9. Combined web + internal research

**Executive context:** Before a regulatory meeting, the CEO wants both external context and
what Keralty already has on file.

**Steps:**
1. *"Investiga las últimas tendencias regulatorias en salud digital en Colombia y compáralas
   con lo que tenemos documentado internamente sobre nuestra estrategia digital."*

**Expected result:** `ResearchAgent` returns a response that clearly distinguishes external
web sources (with URL/domain/date) from internal Drive sources (with filename/excerpt), combined
into one coherent answer — with no `400 INVALID_ARGUMENT` tool error.

**Validates:** the `WebSearchAgent` `AgentTool` wrapper (isolating `google_search` from custom
tools), combined web+Drive synthesis.

---

## 10. Morning inbox triage

**Steps:**
1. *"Revisa mi bandeja de entrada y clasifica los correos por prioridad."*

**Expected result:** Threads classified CRÍTICO / ALTO / MEDIO / BAJO with a suggested action
per thread, presented as a table.

**Validates:** `EmailAgent`'s triage logic, `email_list`/`email_search`.

---

## 11. Drafting and sending an email — with approval

**Steps:**
1. *"Redacta un correo para el equipo de Colombia informando sobre el cierre del trimestre."*
2. Review both the short and full versions offered.
3. Approve.

**Expected result:** A draft is created in Gmail first (`email_draft`), an approval card is
shown with the full content, and `email_send` only fires after `[APROBADO]` — never before.

**Validates:** `EmailAgent`'s mandatory approval gate, audit logging of the send.

---

## 12. Tracking a commitment and following up

**Steps:**
1. After sending an email: *"Haz seguimiento a este correo."*
2. Later: *"¿Qué correos tengo en seguimiento?"*
3. Open the **Correo Ejecutivo** page and check the "Seguimiento" tab and indicator.

**Expected result:** A tracking record is created; it's retrievable via chat and via the live
dashboard indicator, consistently. The dashboard's "Seguimiento" tab shows the **real subject
and recipient** of the tracked email (e.g. "test - urgent" / "Para: ...") — never the raw
Gmail message ID. This works even for records tracked before this behavior existed: the
dashboard self-heals by looking the subject up live from Gmail if it's missing from the stored
record.

**Validates:** `email_track`/`email_get_tracking` (now capturing `subject`/`to` at tracking
time via `GmailProvider.get_message_headers`), `/api/email/summary`'s self-healing enrichment
for legacy records, the `email_tracking` Firestore collection.

---

## 13. Reviewing today's email dashboard

**Steps:**
1. Open **Correo Ejecutivo**.
2. Check that **Bandeja**, **Críticos**, **Pendientes**, and **Seguimiento** show real numbers,
   not placeholders.
3. In the **Bandeja de Entrada** tab, confirm each email shows a small colored priority badge
   (CRÍTICO / ALTO / MEDIO / BAJO) next to the sender — not just Gmail's generic flags.
4. Click **Actualizar**, ideally while your system clock/timezone is set somewhere other than
   Colombia, to confirm "today" reflects *your* current local day rather than a fixed timezone.

**Expected result:** All four indicators populate from real Gmail queries and the Firestore
tracking collection — not hardcoded `'—'` values — and reflect your own current calendar day
regardless of where you're logged in from (the frontend sends your browser's live timezone on
every request). Each inbox item's priority badge reflects the same CRÍTICO/ALTO/MEDIO/BAJO
judgment the chat-based EmailAgent uses, not just Gmail's `is:important` flag — items should be
visibly differentiated (a real "urgente" request should not carry the same badge as a casual
greeting). If any part of the fetch fails (e.g. an expired token), an orange warning banner
appears above the tabs instead of the tiles silently showing "0".

**Validates:** `GET /api/email/summary?tz=...`, timezone-correct epoch-based Gmail queries
(`_local_midnight_epoch`), `services/email/triage_service.py`'s batched Gemini classification,
the `warnings` field and its frontend banner, the credential-loading helper for plain REST
endpoints.

---

## 14. A live voice conversation

**Steps:**
1. Click the microphone icon in the chat input.
2. Speak a request, e.g. *"¿Cuáles son mis correos pendientes de hoy?"*
3. Wait for the transcript to appear and auto-submit.

**Expected result:** The mic connects (no immediate disconnect), a live transcript streams in,
and it auto-submits as a normal chat message once you finish speaking.

**Validates:** the Gemini Live API session (TEXT-modality-compatible model), the WebSocket
URL construction (`wss://` in production), the audio worklet pipeline.

---

## 15. Managing conversations like a modern chat app

**Steps:**
1. Click **Nueva conversación** — confirm the chat view clears completely.
2. Have a short exchange, then click **Nueva conversación** again.
3. Click back on the first conversation in the sidebar — confirm the full thread reloads
   inline, instantly, with no page reload.
4. Hover a conversation and delete it.

**Expected result:** Every action above works without navigating away from the main chat view;
conversations are grouped under Hoy / Ayer / Últimos 7 días / Anteriores; "Nueva conversación"
genuinely starts a fresh session rather than silently reusing the old one.

**Validates:** `ChatSessionProvider` (shared context), the sidebar's live history fetch, the
Firestore composite indexes backing `GET /history/`.

---

## 16. Continuing a task across an approval

**Executive context:** The CEO starts a request, has to step away before approving, and comes
back later — potentially after switching to a different conversation in between.

**Steps:**
1. Start a Doc-editing or email-send request that requires approval.
2. Before approving, switch to a different conversation in the sidebar.
3. Switch back to the original conversation.
4. Approve the pending task.

**Expected result:** The pending approval card is still there and still actionable after
switching away and back; approving it correctly resumes the original agent's buffered action.

**Validates:** `GET /api/tasks` polling independent of which conversation is currently loaded,
Firestore-backed task state surviving session switches.

---

## 17. Admin oversight

**Executive context:** IT/operations needs visibility into how the assistant is being used
across the organisation.

**Steps:**
1. Open **Administración → Métricas** — confirm real counts (sessions, messages, users, audit
   events).
2. **Usuarios** — confirm the user list loads with real accounts.
3. **Knowledge Base** — upload a PDF and a Markdown file; confirm both index successfully and
   show a chunk count.
4. **Auditoría** — confirm recent write actions (the Doc/Sheet/email actions from earlier
   scenarios) appear with color-coded action badges.
5. **Configuración** — confirm feature flags reflect the actual deployed configuration.

**Expected result:** All five tabs load without 403s; KB ingestion succeeds for both a
plain-text-heavy Markdown file and a real-world PDF (including one with tables or dense
formatting, which previously could exceed embedding token limits).

**Validates:** `ADMIN_PANEL_ENABLED`, the RAG chunker/embedder reliability fixes, GCS bucket
provisioning, audit logging coverage.

---

## 18. Attaching a document via the paperclip picker _(known limitation)_

**Steps:**
1. Click the paperclip icon in the chat input and search for a file you own.

**Current expected result:** This will likely show **"No documents found"** even for files you
own, because this specific endpoint doesn't yet use your personal Drive credentials — it only
sees files owned by the backend's service account. This is a known, tracked gap (see
`docs/product-roadmap-new-features.md`, Tier 0.4), not a new regression. Use scenario 4's
`drive_search`-based approach in chat instead, which works correctly today.

**Validates:** confirms the gap is still present (or that it's been fixed, if this scenario now
succeeds — update this document if so).

---

## 19. Bilingual operation

**Steps:**
1. Toggle the language switcher (ES/EN) in the top navigation.
2. Ask the same question in English: *"What are Keralty's strategic priorities this year?"*

**Expected result:** The UI and the assistant's response language both switch correctly; the
**site language (ES/EN toggle) drives the reply language** — with the UI in English, replies
come in English even if the question was typed in Spanish, and vice versa. (This changed in
July 2026: previously the assistant matched the message's language regardless of the toggle.)

**Validates:** `next-intl` locale routing, the `locale` field on `POST /api/chat`, the
per-turn language system note in `routers/chat.py`.

---

## 20. Generating a follow-up draft directly from the dashboard

**Executive context:** The CEO is scanning the "Seguimiento" tab between meetings and wants to
nudge someone without opening Gmail or starting a chat conversation.

**Steps:**
1. Open **Correo Ejecutivo → Seguimiento**.
2. Click **Generar seguimiento** on any tracked item.

**Expected result:** A real Gmail draft is created (threaded to the original conversation), and
the actual generated subject and body appear inline on the dashboard immediately — not just a
generic "created" confirmation. The body should read as a genuine, topic-aware follow-up
referencing the original email's subject, not a generic canned template repeated verbatim
across different tracked items. No email is sent — this only ever creates a draft, matching the
same security model as `email_draft` (nothing sends without a separate, explicit approval).

**Validates:** `POST /api/email/tracking/{id}/generate-followup`,
`services/email/followup_service.py`'s Gemini-personalized body generation, that
`thinking_config=ThinkingConfig(thinking_budget=0)` is actually applied (without it, this call
previously returned a response truncated to a few words).

---

## 21. Delegating without asking permission, and switching tasks mid-conversation

**Executive context:** The CEO gives the assistant a multi-step request, then — in the same
conversation — asks for something completely unrelated to what the last agent was doing.

**Steps:**
1. *"Busca información sobre energías renovables en Colombia y luego crea un resumen ejecutivo
   con eso."*
2. Observe the assistant's first response.
3. In a **later message in the same session**, after the assistant has been doing something
   narrow (e.g. editing a specific document), ask for something unrelated to that agent's job —
   e.g. if it was just editing a Doc, ask it to create a brand-new spreadsheet instead.

**Expected result:** Step 2: the assistant announces its plan in one sentence (e.g. "Voy a usar
ResearchAgent para buscar fuentes externas y luego AnalysisAgent...") and proceeds immediately
— it must **not** ask "¿te parece bien si...?" or otherwise wait for permission to pick which
agent to use. Step 3: the assistant must **not** claim it lacks the capability (e.g. "no puedo
crear hojas de cálculo nuevas" would be wrong if the request just needs a different agent) — it
should hand off to the correct agent and actually attempt the new task.

**Validates:** the orchestrator's "announce and proceed, never ask permission to delegate"
instruction, and every sub-agent's `# LÍMITES Y TRANSFERENCIA DE ALCANCE` block that hands
control back to `OrchestratorAgent` instead of refusing — this specifically guards against
ADK's sticky turn-routing (the next message goes to whichever agent handled the last one, not
back through the orchestrator by default).

---

## 22. Hearing a reply read aloud

**Executive context:** The CEO is reviewing replies hands-free while doing something else and
wants to hear a specific answer instead of re-reading it.

**Steps:**
1. Ask the assistant anything and wait for a finished (non-streaming) reply.
2. Click the small speaker icon under the assistant's message.
3. While it's playing, click the speaker icon on a **different** message.

**Expected result:** Clicking the icon plays real generated audio — genuine, natural-sounding
speech in the message's actual language (Spanish text should sound like Spanish, not an
American accent reading Spanish phonetically). Nothing plays automatically; playback only ever
starts on click, for any message (not just ones that started as a voice question). Step 3 stops
the first message's audio and starts the second — only one message plays at a time.

**Validates:** `POST /api/tts`, Gemini's native multilingual TTS (`GEMINI_TTS_MODEL`), that the
backend correctly wraps the raw PCM response in a playable WAV file, and the per-message
`playingMessageId` state in `ChatWindow.tsx`.
