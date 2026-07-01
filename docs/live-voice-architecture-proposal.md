# Proposal: True Real-Time Voice Conversation with Full Agent Capabilities

_Written 2026-07-02. For team discussion — not scheduled, not implemented. Scoped in response
to a request for a genuinely live, low-latency spoken conversation with Keralty Assistant that
retains full access to Docs/Sheets/Slides/Gmail/Knowledge Base/HITL approvals during the voice
session itself._

---

## What exists today (as of this document)

The current voice feature is **speech-to-text input, full agent turn, text-to-speech output** —
not a live conversation:

1. User speaks → audio streams to `routers/voice.py` → a Gemini Live API session (configured
   for `input_audio_transcription` only) returns a text transcript of what the user said.
2. That transcript is submitted as a normal typed message through the existing `/api/chat` SSE
   pipeline — the full `OrchestratorAgent` → sub-agent → tool-calling → HITL approval flow runs
   exactly as it does for typed input. Every capability works.
3. Once the text reply is fully generated, the browser's own `speechSynthesis` API reads it
   aloud.

This is deliberately conservative: it adds a spoken layer on top of an unchanged, fully-capable
text pipeline, at the cost of a conversational rhythm that follows "listen → think → full agent
turn → speak" rather than a fluid back-and-forth. Round-trip latency is bounded by the slowest
part of a normal chat turn (multi-agent orchestration, RAG retrieval, Workspace API calls),
which can be several seconds — noticeably slower than a natural conversation's turn-taking.

---

## What "true live audio-to-audio with tool access" actually requires

### 1. A continuously-open Gemini Live session with function calling

Gemini's Live API supports `tools=[...]` in `LiveConnectConfig` — the same
`FunctionDeclaration` shape used everywhere else — so a live session **can** call functions
mid-conversation and keep talking once it has a result. This is the mechanism that would replace
today's "transcribe, then hand off to a separate text pipeline" design.

The open question is **what those tools are**. Two sub-options:

- **Flatten every agent's tools into one set** exposed directly to the Live session. Simple to
  wire, but loses the Orchestrator's routing intelligence and each sub-agent's specialized
  system instructions (e.g. `EmailAgent`'s triage logic, `WritingAgent`'s document structure
  rules) — the Live session's own system instruction would have to absorb all of that.
- **Wrap each sub-agent as a callable tool via `AgentTool`** (the same pattern already used to
  isolate `google_search` inside `WebSearchAgent` for `ResearchAgent` — see `research_agent.py`
  and the "Important ADK constraint" note in the Architecture section of `CLAUDE.md`). The live
  session's model becomes a thin conversational front-end that calls
  `AgentTool(analysis_agent)`, `AgentTool(writing_agent)`, etc., and each retains its full
  instruction set and tool access. This preserves the existing agent architecture but adds a
  translation layer between the Live API's function-calling protocol and ADK's own
  `Runner`/session-state model, which isn't built for a persistent bidirectional audio session
  today.

### 2. Full audio playback on the frontend

`VoiceChat.tsx` today only **captures** microphone audio — there is no speaker output pipeline
at all (the AudioWorklet's output is explicitly not connected to the audio destination). A live
conversation needs the model's streamed audio response played back with proper buffering, and
**interruption handling**: Gemini Live's voice activity detection can signal that the user
started talking while the model is still speaking, which needs to immediately stop local
playback — this is meaningfully more complex than triggering `speechSynthesis.speak()` once on
a finished string.

### 3. A redesigned approval flow for voice

The existing HITL pattern (`approval_create` → Firestore task → frontend polls
`GET /api/tasks` → user clicks an `ApprovalCard` → `[APROBADO] task_id=...` submitted as the next
chat message) assumes a visual, click-driven confirmation step. That doesn't fit naturally into
a live spoken exchange. Real options, requiring a product decision, not just an engineering one:

- **Spoken confirmation**: the model asks "¿confirmas que envíe el correo?" and a "sí"/"no"
  response (captured via the same live transcript) drives the approval — but this needs a
  reliable way to disambiguate genuine confirmation from the user just continuing to talk, and
  an audit-safe way to record that a spoken "yes" constitutes the same approval a click does
  today.
- **Fall back to the visual card**: pause the live audio turn, surface the existing
  `ApprovalCard` in the chat UI as today, and resume the live session once the user approves via
  click. Keeps the audit/approval semantics unchanged but breaks the "fluid conversation" feel
  exactly at the moment it matters most (any Workspace write or email send).

**No exceptions to the approval guardrail should be considered acceptable** regardless of which
option is chosen — per the orchestrator's existing guardrail, no write action should ever
execute without a recorded, explicit approval.

### 4. Session lifecycle & cost

A live session held open for the duration of a conversation is a different cost/operational
shape than today's per-turn request: needs idle-timeout handling, reconnect-on-drop logic
(Cloud Run's default request timeout and any load balancer idle timeout both need checking
against realistic conversation lengths), and Vertex AI billing for a live audio session is
typically higher than equivalent turn-based text/audio calls — worth getting an estimate before
committing engineering time.

---

## Recommended approach for team discussion

Rather than committing to full scope immediately, two viable middle grounds:

**A. Read-only live voice, write actions stay text-mediated.** Let the live session directly
answer questions and read from the Knowledge Base / Drive / Sheets / calendar-style lookups in
real time (no approval needed for reads), but the moment a write action is needed ("send this
email", "create this doc"), the model tells the user it's preparing that and hands off to the
existing visual approval flow, exiting the live loop. This avoids the hardest open problem
(voice-driven approval semantics) while still delivering a genuinely fluid conversation for the
majority of "ask a question" interactions.

**B. Full bridge, phased.** Build the `AgentTool`-wrapped bridge for one agent first (e.g.
`KnowledgeAgent`, since it's read-only and highest-value for a "talk to it" experience), prove
out audio playback + interruption handling end-to-end, then extend to write-capable agents once
the approval-flow question is resolved.

Both require: an audio playback pipeline (item 2 above) and a decision on tool-bridging
(item 1). Option A defers item 3 entirely; Option B confronts it early but incrementally.

---

## Rough effort estimate

This is not a quick follow-up fix. For scoping purposes:

- Audio playback + interruption handling (frontend): multi-day.
- Tool-bridging layer, `AgentTool`-wrapped or flattened (backend): multi-day, more if
  flattening/re-instructing rather than reusing existing agents as-is.
- Approval-flow redesign for voice (product + engineering): needs a product decision before
  estimating engineering effort; likely multi-day on its own.
- End-to-end testing of a fundamentally different interaction pattern (no existing test
  precedent for this in the repo — see the "No automated test suite" gap in
  `docs/product-roadmap-new-features.md`, Tier 0.2).

Total: likely **multi-week**, not a single sprint item, and touches product/UX decisions the
engineering team can't resolve alone (especially the approval-flow question).

---

## Open questions for the team

1. Is a spoken "yes" an acceptable approval mechanism for Workspace writes / email sends, or
   must every write still go through a visual click? (Compliance/audit implications.)
2. Is Option A (read-only live voice, writes stay text-mediated) an acceptable first version, or
   does the value proposition require write actions to work in voice from day one?
3. Which agents/capabilities are highest-priority for a live voice experience — is this meant to
   replace typed chat entirely, or specifically serve a "hands-free while commuting" use case
   (per the original Multi-Modal Input roadmap item) where read-only queries dominate?
4. What's the acceptable cost ceiling for a live audio session vs. today's turn-based cost, given
   Vertex AI's audio-session pricing is typically higher?
