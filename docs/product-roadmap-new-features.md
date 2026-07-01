# Keralty Assistant — Product Roadmap: Next-Generation Capabilities

_Written 2026-07-01. Supersedes and replaces the 2026-06-30 draft — corrected against the actual
GCP project configuration and codebase, not assumptions. This is forward-looking: everything
below is scoped to begin **after** the current development cycle (Sheets/Drive tooling, RAG
reliability fixes, voice pipeline fix, sidebar/history redesign, branding) is complete and
stable in production._

---

## Strategic Framing

The current system is a **reactive assistant**: the executive asks, the agent answers or
creates. That covers perhaps 20% of the executive's cognitive burden. The remaining 80% is the
work nobody asks about but everyone drowns in: tracking commitments made across fragmented
conversations, preparing for the next meeting, monitoring the operational health of nine
countries, staying ahead of regulation, and synthesising fragmented signals into decisions.

This roadmap moves Keralty Assistant from a reactive tool into a **proactive executive
intelligence layer** — one that surfaces the right information before it's asked for, tracks
obligations so nothing falls through the cracks, and acts as institutional memory across the
entire organisation.

Features are grouped by the executive value they unlock, not by technical module. Each section
states the problem it solves, why it matters specifically for Keralty, and what must be built —
including, where relevant, what already exists today and can be reused rather than rebuilt.

---

## Current Platform State (baseline as of 2026-07-01)

So this roadmap isn't re-proposing what already exists, and so future readers have accurate
context without re-deriving it:

**Already built and working:**
- Orchestrator + 8 specialised sub-agents (Analysis, Research, Writing, Editing, Review,
  Visual, Email, Knowledge), all on Google ADK.
- Full Google Workspace read/write: Drive, Docs, Sheets (including raw uploaded `.xlsx`/`.xls`
  files, not just native Google Sheets), Slides, Gmail — with mandatory human-in-the-loop
  approval before any Workspace write or email send.
- Hybrid RAG knowledge base (BM25 + dense embeddings + Gemini reranking + abstention gate),
  with admin-gated document ingestion (PDF/DOCX/CSV/TXT/MD).
- Real-time voice conversation via the Gemini Live API.
- Image generation (Imagen 3) with in-chat download.
- Admin panel: platform metrics, user management, KB document management, audit log,
  feature-flag view.
- Persistent sidebar (Claude.ai/ChatGPT-style): grouped conversation history, inline switching,
  delete, working "new conversation."
- Keralty brand identity applied throughout (official palette, logo, Calibri-compatible
  typography).
- Email dashboard with live inbox/critical/pending/follow-up indicators.

**Known foundational gaps that this roadmap must account for:**
- **No per-user role-based access control exists anywhere.** The admin panel is a single
  global on/off switch (`ADMIN_PANEL_ENABLED`) — every authenticated user gets full admin
  access once it's on, or none at all. `users.role` in Firestore is an unenforced free-text
  field.
- **No automated test suite.** The only precedent in the repo is ad-hoc one-off scripts.
- **Observability is console-log-based, not structured.** `OTEL_ENABLED` defaults off, and
  error handling throughout the codebase is `print(...)`, not a metrics/alerting pipeline.
- **The DocumentPicker (`/documents` endpoint) never threads the logged-in user's OAuth
  credentials** — it only ever sees files owned by the backend's service account, not the
  user's own Drive.
- **Calendar, Cloud Scheduler, and Cloud DLP APIs are not enabled** in the `keraltysandbox` GCP
  project (verified directly — several planned features below depend on one of these).

---

## Tier 0 — Platform Foundations

_These aren't optional infrastructure footnotes — they're blocking dependencies for multiple
Tier 1/2 items below, and are substantial enough to be scheduled as real work, not assumed as
free._

---

### 0.1 Role-Based Access Control

**Problem:** Several planned features (personalized dashboards, team collaboration, document
classification enforcement, executive-vs-CoS visibility) assume a user's role determines what
they can see and do. Today that assumption is false — there is no code path anywhere that reads
or enforces a role.

**What must be built:**
- A real `role` claim, set at login (or looked up from Firestore `users.role` on each
  authenticated request) and attached to `request.state.user`.
- Per-endpoint authorization checks in `routers/admin.py` and `routers/knowledge.py` (currently
  gated only by the global `ADMIN_PANEL_ENABLED` flag) that also check the caller's role.
- A defined role taxonomy for Keralty's structure (e.g., `executive`, `chief_of_staff`,
  `country_vp`, `admin`) agreed with the business before implementation — this is a
  product decision, not just an engineering one.

---

### 0.2 Automated Testing & CI Pipeline

**Problem:** Every fix made in the current development cycle was found by manually exercising a
feature end-to-end against the live deployment — there is no automated way to catch a
regression before a user does. As this roadmap adds scheduled jobs, webhooks, and five-plus new
agents, the blast radius of an untested change grows substantially.

**What must be built:**
- A `tests/` suite (pytest) covering at minimum: the RAG chunking/embedding pipeline (the exact
  class of bug that broke PDF ingestion this cycle), Firestore query paths (composite index
  mismatches broke conversation history silently for an unknown period), and the HITL approval
  state machine.
- A CI step (Cloud Build trigger or GitHub Actions) that runs the suite on every PR before
  deploy.
- At least smoke-test coverage for every new agent/tool added under this roadmap before it
  ships.

---

### 0.3 Structured Observability & Alerting

**Problem:** Several bugs fixed this cycle (a missing GCS bucket silently breaking image
generation and KB uploads, Firestore composite index mismatches silently 500ing conversation
history) were invisible until a person happened to trigger them manually. A system built to be
*proactive* about the executive's work cannot itself be blind to its own failures.

**What must be built:**
- Turn on `OTEL_ENABLED` in production and wire real spans around every tool call, not just the
  scaffold that exists today.
- Replace `print(...)` error handling with structured logging (Cloud Logging severity levels)
  across `tools/`, `services/`, and `routers/`.
- Cloud Monitoring alerting policies for: 5xx rate per endpoint, GCS/Firestore call failures,
  and Gemini/Vertex API error rates — so a broken dependency pages someone instead of waiting
  for a user report.

---

### 0.4 Drive Access Parity

**Problem:** The DocumentPicker (paperclip attachment in chat) only ever lists files the backend's
service account owns — never the logged-in user's own Drive — because `routers/documents.py`
never threads their credentials through, unlike every other Workspace-touching endpoint.

**What must be built:**
- Thread the same `_credentials(tool_context)` pattern already used everywhere else into
  `routers/documents.py`'s three endpoints.
- This directly unblocks Tier 1 Item 5 (Document Intelligence) and Tier 2 Item 11
  (Cross-Document Portfolio Intelligence), both of which assume reliable access to a user's own
  Drive content.

---

## Tier 1 — Must-Have (Game-Changers for Daily Executive Workflow)

---

### 1. Calendar Intelligence & Meeting Agent

**Problem:** Executives at Keralty spend the majority of their working day in meetings. Today
the assistant knows nothing about the calendar. Every meeting begins with the executive having
to mentally reconstruct context.

**Why it matters for Keralty:** With operations in 9+ countries across multiple time zones,
executives routinely meet stakeholders whose history spans months of email threads, shared
documents, and previous commitments. Preparing for a meeting with the CFO of Colombia, the
regulatory director in Mexico, or an external partner currently requires manual digging.

**Prerequisite (corrected from the prior draft):** the Google Calendar API is **not** currently
enabled in the `keraltysandbox` project — this needs to be enabled first, and a `calendar`
scope added to `auth/google_oauth.py`'s `SCOPES` list. Adding a scope forces every
already-logged-in user to re-consent, since their stored credentials won't carry it — plan the
rollout communication accordingly.

**Capabilities to build:**

- **Pre-meeting intelligence brief:** Ten minutes before a calendar event, proactively send a
  brief with: who the participants are (from KB and email history), what was last discussed
  with them, any outstanding commitments from previous interactions, relevant documents created
  in the last 30 days mentioning the meeting topic, and key metrics the executive should know.
  Triggered automatically by the Calendar API.

- **Post-meeting action extractor:** After a meeting, accept meeting notes (pasted, uploaded,
  or eventually from Google Meet transcript) and extract: action items with owners and
  deadlines, decisions made, follow-up emails to draft, documents to create. Store action items
  persistently and surface them in the commitment tracker (Item 3).

- **Smart scheduling:** "Find a time that works for five people this week, avoid Friday
  afternoon, and leave at least 30 minutes before any meeting with the board." Uses
  `calendar.freebusy`.

- **Meeting preparation packages:** "Prepare me for the Q3 board review." Agent aggregates the
  last quarter's performance spreadsheets, pending decisions, key risks from email, and
  generates a briefing deck automatically (reuses the existing `VisualAgent`/Slides pipeline).

**New agent:** `CalendarAgent`. **New tools:** `calendar_get_upcoming`,
`calendar_get_meeting_context`, `calendar_create_event`, `calendar_freebusy`.

---

### 2. Proactive Daily Executive Brief

**Problem:** The assistant currently waits to be asked. Every morning an executive faces a fresh
inbox, a full calendar, and pending decisions — but must manually ask the assistant for each
piece of information.

**Why it matters for Keralty:** Senior executives at a multinational health company face a
morning fragmentation problem: 50+ emails across 9 countries, board-level decisions pending,
regulatory updates from multiple jurisdictions, and an operational dashboard showing 9 markets
simultaneously. A daily brief synthesises this before the day starts.

**Prerequisite:** Cloud Scheduler is not enabled in the project — needs enabling, plus a Cloud
Run job (headless invocation of the `OrchestratorAgent`) and a delivery mechanism (see below).

**Capabilities to build:**

- **Automated morning brief at a configurable time** (e.g., 6:30 AM local time): delivered via
  the app or email. Contains: top 5 emails requiring action (reusing the email indicator logic
  already built for the Email dashboard), meetings scheduled for the day with auto-generated
  context (Item 1), pending HITL approvals from the previous day (`GET /api/tasks` already
  exists), monitored KPI anomalies (Item 6), commitments due today/tomorrow (Item 3), and a
  one-paragraph strategic/regulatory context paragraph.

- **Configurable brief preferences:** persisted per-user (see Item 4's preference layer).

- **Implementation:** Cloud Scheduler → Cloud Run job → `OrchestratorAgent` headless run →
  result written to Firestore and delivered via Firebase Cloud Messaging (web push) or Gmail.

---

### 3. Commitment & Action Item Tracking

**Problem:** Executive conversations — email, meetings, documents — are full of commitments:
"I'll send you the report by Friday," "we agreed to review the budget by end of month," "John
will get back to you with the contract." These commitments are scattered across systems,
remembered only by the person who received them, and regularly dropped.

**Why it matters for Keralty:** A multinational healthcare company runs on regulatory
commitments, supplier commitments, intergovernmental agreements, and internal executive
promises. A dropped commitment in a regulatory context in Colombia or Mexico can have legal
consequences.

**Prerequisite:** real-time email monitoring needs a Gmail `watch()` push subscription, which
requires a Pub/Sub topic and a renewal job (watches expire after 7 days). Pub/Sub is already
enabled in the project — but nothing currently uses it, so this is genuinely new wiring, not a
head start.

**Capabilities to build:**

- **CommitmentAgent (new agent):** Monitors email threads as they arrive (Gmail push
  notification), extracts commitments made or received, classifies them (due date, owner,
  counterparty, topic), and stores them in a `commitments` Firestore collection.

- **Commitment dashboard:** commitments made, commitments owed to the executive, overdue items,
  color-coded by urgency — extends the pattern already built for the Email dashboard's
  indicators.

- **Proactive reminders and follow-up generation:** reuses the existing
  `email_generate_followup` tool pattern already built for tracked emails.

- **Completion detection:** when a document is created or email sent that fulfils a tracked
  commitment, mark it complete automatically.

- **Tools needed:** `commitment_extract(text)`, `commitment_create`, `commitment_list`,
  `commitment_update_status`. New Firestore collection: `commitments` (remember to provision
  the correct composite index for whatever field the list query actually orders by — this
  exact class of mismatch silently broke conversation history for a period this cycle).

---

### 4. Long-Term Conversational Memory & Executive Preferences

**Problem:** Every conversation with the assistant currently starts from scratch. The executive
must re-establish context every time: "the Colombia expansion is our top priority," "I prefer
bullet summaries under 5 points," "always CC María García on anything going to the board." None
of this persists.

**Why it matters for Keralty:** Executive workflow depends on accumulated institutional
knowledge — who the key people are, this quarter's strategic priorities, preferred report
formatting, communication style. A personal AI assistant without persistent memory isn't
personal.

**Capabilities to build:**

- **Preference memory layer:** explicit ("remember I always want reports under 2 pages") and
  implicit (learned from repeated corrections) preferences in a new `user_preferences`
  Firestore collection.

- **Project & priority context:** "our top 3 priorities this quarter are X, Y, Z" persists
  across sessions and gets injected into relevant agent contexts automatically.

- **People memory:** "Carlos Rodríguez in Colombia is my go-to for regulatory matters, prefers
  formal Spanish" — stored in a new `user_contacts` collection, auto-injected when that person
  appears in email or documents.

- **Strategic framing injection:** the orchestrator retrieves current priorities, constraints,
  and preferences from Firestore and injects them before processing every task.

- **Memory commands:** "forget what I said about the Mexico timeline," "update my priority,"
  "what have you remembered about me?"

---

### 5. Document Intelligence Pipeline — Contracts & Reports

**Problem:** Healthcare companies deal with enormous volumes of contracts: supplier agreements,
insurance contracts, regulatory filings, clinical partnerships — typically 20-100 page PDFs
executives cannot read in full but must understand.

**Why it matters for Keralty:** Keralty manages contracts with governments, hospital networks,
insurance companies, pharmaceutical suppliers, and technology vendors across 9 countries. The
executive needs contract intelligence in minutes, not hours.

**Corrected scope:** the chunk → embed → store pipeline this needs already exists
(`services/rag/chunker.py`, `embedder.py`) and was hardened this cycle (fixed an unbounded
chunk-growth bug and an embedding-batch token-overflow bug — both specifically triggered by
PDFs, not clean text). This item should **reuse that pipeline in a session-scoped mode**
(skip the permanent KB write/admin gate) rather than building new extraction/chunking
infrastructure. The genuinely new work is narrower than the original draft implied:

**Capabilities to build:**

- **Session-scoped ingestion:** accept a file upload or Drive file ID, run it through the
  existing extract → chunk → embed pipeline, but hold results in-memory/session-state instead
  of writing to the permanent `kb_chunks` collection (unless the user explicitly asks to add it
  to the KB).

- **Contract analysis tools:** `contract_extract_parties`, `contract_extract_obligations`,
  `contract_extract_dates`, `contract_identify_risks` — genuinely new, used by `AnalysisAgent`.

- **Contract comparison:** "compare our Colombia and Mexico MSAs on liability and termination" —
  multi-document analysis across two ingested contracts.

- **Clause library:** flag clauses that deviate from Keralty's standard templates (once
  standard templates exist in the KB).

- **Frontend:** a document upload dropzone in `ChatWindow`, extraction status, and a contract
  summary card with key dates highlighted.

- **Depends on:** Tier 0.4 (Drive access parity), so a contract already sitting in the
  executive's own Drive can actually be read.

---

### 6. Scheduled Automation & Proactive Agents

**Problem:** The assistant can only respond to requests. Much of executive intelligence work is
periodic and predictable: weekly performance review, monthly regulatory digest, quarterly board
prep. Today the executive must manually initiate every one of these.

**Why it matters for Keralty:** A healthcare holding company with 9 country operations needs
regular structured reviews. Time spent assembling weekly status reports and cross-referencing
spreadsheets is enormous and low-value.

**Prerequisite:** Cloud Scheduler is not enabled — same dependency as Item 2; build both against
the same scheduling infrastructure rather than two separate mechanisms.

**Capabilities to build:**

- **Scheduled agent runs:** user-defined recurring tasks stored in a new `scheduled_tasks`
  Firestore collection, triggered by Cloud Scheduler, delivered via app or email.

- **Drive change monitoring:** "alert me when any file in /Board/Q3 is modified" — Drive push
  notification webhook.

- **Spreadsheet threshold alerts:** scheduled read-check against a configured cell/range,
  building directly on the Sheets read tooling already in place (including the raw-Excel
  support added this cycle).

- **KPI monitoring agent (new `MonitoringAgent`):** periodically reads executive-defined
  spreadsheets, surfaces anomalies (week-over-week drops, out-of-range values, missing data).

- **Automated report generation:** scheduled multi-spreadsheet synthesis, delivered to the exec
  team.

---

### 7. Healthcare Regulatory Intelligence Monitor

**Problem:** Keralty operates in 9 countries, each with its own evolving health regulatory
framework. Keeping up is a full-time job, and compliance failures have catastrophic consequences
in healthcare.

**Why it matters for Keralty:** Colombia (MSPS), Mexico (COFEPRIS), and Peru (DIGEMID) all issue
significant regulatory updates regularly. Missing a filing deadline can mean license suspension.

**Capabilities to build:**

- **Regulatory watch feeds (new `RegAgent`):** monitors configured regulatory sources per
  country, reusing `ResearchAgent`'s existing web search capability (the `AgentTool`-wrapped
  `WebSearchAgent` built this cycle) targeted at specific domains and RSS feeds.

- **Impact analysis:** what changed, which Keralty operations are affected, what action and
  deadline — a structured alert, not a raw summary.

- **Regulatory calendar:** tracks known filing deadlines, surfaced in the daily brief (Item 2)
  with lead times.

- **Document alignment check:** compares an internal policy (from Drive) against a regulation
  (from KB/web) and flags gaps.

---

### 8. Multi-Modal Input — Voice Memos, Images, PDFs

**Problem:** Executives generate insights in non-digital contexts: whiteboard sessions, voice
notes during a commute, physical documents. The assistant currently accepts only typed text (and,
as of this cycle, live voice conversation).

**Why it matters for Keralty:** Executive thinking happens between meetings, in transit, on
calls.

**Corrected baseline:** the live voice conversation feature (Gemini Live API) was completely
non-functional until this cycle — two separate bugs (an invalid WebSocket URL scheme, and a
Gemini Live model that rejected the requested text-transcript modality) are now both fixed and
verified working. This item builds on a genuinely solid foundation now, not an assumed one.

**Capabilities to build:**

- **Voice-to-action:** a recorded (not live) voice memo, transcribed and then processed:
  "create action items from this," "draft a document based on what I said."

- **Image/whiteboard capture:** upload a photo; Gemini's multimodal input extracts text,
  diagrams, structure. This is genuinely new — `image_tools.py` today only *generates* images
  (Imagen 3), it has no image-understanding path at all.

- **PDF drop-in:** shares infrastructure with Item 5's session-scoped ingestion.

- **Email forwarding to agent:** a dedicated inbound address the executive can forward emails
  to for summary/action-item processing.

---

### 9. Executive Intelligence Dashboard (Single Pane of Glass)

**Problem:** The interface is a chat window (now with a persistent conversation sidebar, as of
this cycle's redesign) but there's still no persistent view of the executive's operational
state: pending approvals, today's meetings, outstanding commitments, monitored KPIs, drafts
awaiting review.

**Why it matters for Keralty:** Senior executives need a command center, not just a chatbot.

**Capabilities to build:**

- **Dashboard page** (`app/[locale]/dashboard/page.tsx`): real-time widgets — Pending Approvals
  (the `GET /api/tasks` data already exists), Today's Meetings (Item 1), Active Commitments
  (Item 3), KPI Watchlist (Item 6), Recent AI Outputs, Email Priorities (reuses the
  `/api/email/summary` endpoint already built).

- **Interactive dashboard:** approve/open/mark-done inline without entering the chat.

- **Configurable widgets:** pin/unpin data sources per executive.

- **Depends on:** Tier 0.1 (role-based access), since different executives should plausibly see
  different widgets/data scope.

---

## Tier 2 — High Value (Significant Capability Additions)

---

### 10. Google Meet Integration — Meeting Intelligence

After a Google Meet call (recording saved to Drive): transcribe via Gemini, extract action
items/decisions/discussion points, generate a structured Google Docs summary (reuses
`docs_create` with content), draft follow-up emails per participant, update the commitment
tracker (Item 3). Trigger: Drive webhook on new recording.

---

### 11. Cross-Document Portfolio Intelligence

- **Semantic search across all Drive:** "find everything on the Colombia expansion from the
  last 6 months" — requires permanent Drive indexing, not just per-session. **Depends on Tier
  0.4** (without real Drive access parity, this can only ever search service-account-owned
  files).
- **Entity resolution:** track mentions of key projects/people/initiatives across documents over
  time.
- **Commitment extraction at scale:** retroactively process 6 months of email/notes to seed the
  Item 3 backlog.

---

### 12. Financial Intelligence Agent

- **New `FinancialAgent`:** interprets financial spreadsheets in business-narrative context —
  builds directly on the Sheets reading tooling (including raw-Excel support) added this cycle.
- **Budget vs. actual analysis, trend synthesis, anomaly explanation** correlating spreadsheet
  data with email/doc context from the same period.

---

### 13. Team Collaboration & Delegation

- **Task delegation** to a Chief of Staff, with Firestore-tracked completion.
- **Shared knowledge:** "publish to team KB" from a personal finding.
- **Review workflows:** async draft review cycles.
- **Role-based access:** CEO sees all, country VP sees their country + group-level, functional
  VP sees their function. **Depends entirely on Tier 0.1** — none of this is buildable without
  the role system existing first.

---

### 14. Multi-Country Context Intelligence

- **Country context tag on every request**, pulling the right regional KB section, regulatory
  framework, team structure.
- **Cross-country comparison agent:** understands the same metric may live in different
  spreadsheets per country.
- **Regional strategy context injection** when drafting country-specific documents.
- **Language calibration:** formal Colombian vs. Mexican Spanish business register — the
  `WritingAgent` instruction needs country-register awareness, not just language detection.

---

### 15. Data Visualization & Charts

- **Chart generation** (Matplotlib/Plotly — not currently a dependency) from spreadsheet data,
  embeddable in documents/presentations or returned inline in chat.
- **Embed real charts in Slides**, not text descriptions — extends `VisualAgent`'s existing
  `slides_add_image` pattern.
- **Inline chat charts** for data-heavy responses.

---

### 16. Security, Classification & PHI Safeguards

**Corrected scope:** audit logging is not a from-scratch build — an `audit_events` Firestore
collection and shared `_audit()` helper already exist and cover most write tools (Docs, Sheets,
email send). The real gap is narrower: Slides creation and KB document ingestion aren't logged
yet. Scope this item accordingly rather than as new infrastructure.

**Capabilities to build:**

- **Automatic PHI/PII detection:** Cloud DLP API is **not enabled** in the project — needs
  enabling first. Scan documents before any tool processes them; warn and refuse to forward
  externally if PHI is detected.
- **Document classification enforcement:** "Confidential" KB documents must not be summarised
  for users without the appropriate role. **Depends on Tier 0.1.**
- **Close the two known audit-logging gaps** (Slides, KB ingestion).
- **Data residency compliance:** per-country data routing rules for regulated content.

---

### 17. Stakeholder Intelligence Layer

- **Relationship history:** "what do I know about Dr. Ramírez from Sura?" — searches email
  history, document mentions, KB.
- **Organisation mapping:** decision-makers needed for a specific approval, combining KB org
  structure with email relationship data.
- **Contact enrichment:** auto-create a light profile in `user_contacts` (shared with Item 4) on
  first contact appearance.

---

### 18. Microsoft Office & Outlook Compatibility

**Corrected scope:** raw Excel (`.xlsx`/`.xls`) reading is **already built** as of this cycle —
`SheetsService` transparently parses uploaded Excel files via `openpyxl`, found and searched via
Drive alongside native Google Sheets. This item is now narrower: **DOCX and PPTX reading** in
the ad-hoc chat flow (not just the admin KB ingestion pipeline, which already has DOCX
extraction but isn't available to `AnalysisAgent`/`drive_read` directly).

**Also corrected:** the config fields (`EMAIL_OUTLOOK_ENABLED`, Azure credentials) existing does
**not** mean Outlook is partially built. `services/email/outlook_provider.py` is an empty stub,
and there is no Outlook-equivalent of `auth/google_oauth.py` at all — the entire OAuth flow
needs building from scratch, same size of effort as the original Google OAuth integration.

**Capabilities to build:**

- **Outlook/Exchange email integration:** full OAuth flow + Microsoft Graph API provider,
  mirroring `GmailProvider`'s interface so `EmailAgent`'s tools work against either backend.
- **DOCX/PPTX reading** wired into `drive_read`/`AnalysisAgent`, not just KB ingestion.
- **Office format output:** generate DOCX from created content when a stakeholder needs Word,
  not Google Docs.

---

### 19. Conversational Analytics for IT/Admin

**Corrected baseline:** the admin panel already exists and is live (metrics, users, KB, audit,
config tabs) — this item extends it rather than building a new surface.

- **Usage analytics:** agent invocation frequency, document creation patterns, failure/
  correction rates — new `analytics_events` Firestore collection.
- **Cost tracking:** token usage and estimated cost per user/agent/day, surfaced in the existing
  admin Métricas tab.
- **Quality signals:** log rejections (full rewrites, rejected drafts) as a quality signal.
- **Latency monitoring:** P50/P95/P99 per agent. **Depends on Tier 0.3** (structured
  observability) — there's no metrics pipeline to source this from yet.

---

### 20. WhatsApp / Mobile Entry Point

Healthcare executives in Latin America use WhatsApp as their primary mobile tool.

- **WhatsApp Business API integration** (Twilio or Meta Cloud API + webhook): text, voice
  messages, and image uploads processed through the standard chat pipeline.
- **Mobile-first workflow:** brief-on-demand while commuting.
- **Approval via WhatsApp:** pending HITL approvals with approve/reject actions, avoiding the
  need to open the web app.

---

## Tier 3 — Future-Oriented (High Potential, Longer Horizon)

---

### 21. Multi-Agent Parallel Workflows

Currently agents run sequentially (orchestrator → one sub-agent at a time). Complex tasks
("prepare the quarterly report") could run `ResearchAgent` + `AnalysisAgent` + `EmailAgent`
concurrently, with `WritingAgent` synthesising all three streams. Google ADK's `ParallelAgent`
primitive supports this directly — significant latency reduction for complex, multi-source
tasks.

---

### 22. Clinical KPI Intelligence (Non-Clinical)

Operational (not clinical) performance data — hospital wait times, bed occupancy, service SLAs
— read from operational Sheets/BI exports. "Which Colombian facility is underperforming on
patient wait times this month?" cross-referenced with staffing/capacity data. **Strictly
operational intelligence, never clinical decision support** — the system must remain
unambiguous about this boundary.

---

### 23. AI-Assisted Contract Negotiation Intelligence

Pull Keralty's historical contracts with the same supplier, identify past concessions, flag
clauses negotiated away previously, suggest negotiation points based on precedent. Builds
directly on Item 5's contract intelligence pipeline.

---

### 24. Executive Personas & Multi-User Sessions

A single session shared by an executive and their Chief of Staff — CoS queues items for
review, executive approves/redirects, shared history with role-appropriate visibility. Replaces
the current 1:1 user-to-session model with a team-scoped session. **Depends entirely on Tier
0.1** (role system) — not meaningfully buildable before it.

---

### 25. Integration with Enterprise Systems (SAP, Salesforce, Epic)

- **SAP HANA:** financial KPIs directly, no manual spreadsheet export.
- **Salesforce Health Cloud:** patient/commercial pipeline context for regional executives.
- **Epic / hospital EHR (read-only, anonymised):** operational metrics only — census, wait
  times, admission rates.
- **Approach:** custom ADK tools via REST APIs or data exports. Read-only metrics retrieval
  only; never write back to clinical systems.

---

## Implementation Sequencing Recommendation

Sequenced by **executive impact per week of development effort**, with foundational work
scheduled where it actually blocks something rather than deferred indefinitely:

| Wave | Features | Executive Value Unlocked |
|---|---|---|
| **Wave 0** (2-3 weeks) | Role-based access control, automated testing, structured observability, Drive access parity | Makes every subsequent wave safe to build on |
| **Wave A** (3-4 weeks) | Calendar integration (incl. API enablement + re-consent flow), Daily brief, Commitment tracker | Transforms daily workflow immediately |
| **Wave B** (4-6 weeks) | Long-term memory, Document intelligence pipeline (reusing existing RAG infra), Dashboard | Makes every interaction smarter |
| **Wave C** (4-6 weeks) | Regulatory monitor, Scheduled automation, Meet integration | Converts from reactive to proactive |
| **Wave D** (6-8 weeks) | Financial agent, Cross-document intelligence, Data viz | Strategic intelligence layer |
| **Wave E** (6-8 weeks) | WhatsApp integration, Multi-country context, Team collaboration | Scale to full executive team |
| **Wave F** (ongoing) | Enterprise system integrations, Clinical KPIs, Parallel agents | Deep enterprise embedding |

---

## Cross-Cutting Requirements (Apply to All New Features)

**Explainability:** every AI-generated insight must cite its source. The executive must be able
to trace "Colombia revenue declined" back to the specific spreadsheet cell and email thread that
generated the conclusion.

**Graceful degradation:** if a data source is unavailable (Drive offline, Gmail rate limited),
the agent must communicate clearly what is and isn't available, rather than silently returning
incomplete information.

**Approval checkpoints:** any action with external visibility (sending an email, sharing a
document, filing a regulatory alert) must pass through an approval step. No exceptions,
regardless of urgency.

**Bilingual throughout:** every new agent, UI component, and notification must support Spanish
and English. Regulatory content may require Portuguese (Brazil) and French (future markets) —
note this touches the RAG embedding/reranking pipeline's language tuning, not just agent
prompts.

**Privacy by design:** every new data source must be evaluated for PHI risk before integration.
Cloud DLP should be part of every new ingestion pipeline once enabled (Item 16).

**Tested before ship:** every new agent or tool gets at least smoke-test coverage under the
Wave 0 CI pipeline before it reaches production — this wasn't true for parts of the current
system, and it's how several of this cycle's silent bugs shipped undetected.

**Observable in production:** every new capability emits structured logs/traces and integrates
with the Wave 0 observability layer — not just a `print()` statement nobody's watching.

**Audit trail for everything:** all new capabilities must write to the `audit_events`
collection — not just for compliance, but to feed the conversational analytics dashboard
(Item 19) that will drive system improvement.
