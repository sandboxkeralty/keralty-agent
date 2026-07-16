import asyncio
import base64
import io
import json
import random
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from google.genai import types
from services.firestore import FirestoreService
from models.schemas import SessionInDB, MessageInDB

router = APIRouter(prefix="/api/chat", tags=["chat"])

_MAX_QUOTA_ATTEMPTS = 4
# Base backoff per retry (seconds); jitter is added on top. Observed 429
# bursts on Vertex dynamic shared quota sometimes outlive the original
# 2s+4s budget, so the ladder now stretches to ~17s worst-case total.
_QUOTA_BACKOFF = [2, 5, 10]

_MAX_ATTACHED_FILES = 5
_MAX_ATTACHMENT_CHARS = 8000
# Image attachments: hard caps chosen around Firestore's 1 MB limit on the
# persisted ADK event doc (the user-message Event serializes inline image
# bytes as base64 inside event_json). 3 images × ≤200 KB compressed ≈ 800 KB
# encoded — safe; anything looser silently breaks conversation-history
# persistence for that turn.
_MAX_IMAGES_PER_MESSAGE = 3
_MAX_IMAGE_INPUT_BYTES = 10 * 1024 * 1024
_IMAGE_TARGET_BYTES = 200 * 1024


def _compress_image(data: bytes) -> bytes:
    """Downscales/re-encodes an image to JPEG ≤ _IMAGE_TARGET_BYTES.

    Steps down (1024px/q75 → 800/q65 → 640/q60) until under budget; returns
    the last attempt regardless so a stubborn image still goes through
    (slightly over budget beats dropping the attachment).
    """
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    out = b""
    for max_dim, quality in ((1024, 75), (800, 65), (640, 60)):
        im = img.copy()
        im.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality)
        out = buf.getvalue()
        if len(out) <= _IMAGE_TARGET_BYTES:
            break
    return out

_EN_WORDS = (" the ", " what ", " can ", " you ", " how ", " please ", " is ", " are ",
             " of ", " to ", " my ", " me ", " about ", " with ")
_ES_WORDS = (" el ", " la ", " de ", " que ", " para ", " con ", " una ", " un ",
             " los ", " por ", " mi ", " sobre ", " y ")


def _is_english(text: str) -> bool:
    """Cheap language sniff for the reply-language hint.

    Prompt rules alone proved insufficient in production: with an all-Spanish
    instruction corpus and Spanish tool results, agents answered English
    questions in Spanish even with a top-priority language rule. A per-turn
    deterministic hint fixes what prompt wording couldn't.
    """
    t = f" {text.lower()} "
    if any(c in t for c in "¿¡áéíóúñ"):
        return False
    en = sum(1 for w in _EN_WORDS if w in t)
    es = sum(1 for w in _ES_WORDS if w in t)
    return en > es and en >= 2


def _is_quota_error(e: Exception) -> bool:
    # Vertex 429s surface through ADK as e.g. `_ResourceExhaustedError` with
    # "429 RESOURCE_EXHAUSTED" in the message; LiteLLM (Claude/OpenAI models)
    # raises litellm.RateLimitError — match by name/message, never by import
    # (the class set is provider-internal and litellm is an optional dep).
    s = f"{type(e).__name__} {e}"
    return ("RESOURCE_EXHAUSTED" in s or "ResourceExhausted" in s or "429" in s
            or "RateLimitError" in s or "rate_limit" in s.lower().replace(" ", "_"))

class AttachedFile(BaseModel):
    text: str = ""
    # Drive metadata, when the file came from Drive: lets agents operate on the
    # real file (Docs/Sheets/Slides tools) instead of only its extracted text.
    # Local uploads send a synthetic "local:<uuid>" id.
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    # Image attachment: base64 (raw or data-URL) — becomes a real inline image
    # part the multimodal model can see. Compressed server-side (_compress_image).
    image_base64: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"
    user_id: Optional[str] = "default-user"
    # UI locale ("es" | "en") — the site language ALWAYS drives the reply
    # language when present; absent only on older cached frontend builds,
    # which fall back to the _is_english message sniff.
    locale: Optional[str] = None
    # Chat folder for NEW conversations (used only at session creation;
    # ownership-validated, invalid ids silently become "no folder").
    folder_id: Optional[str] = None
    attached_files: Optional[List[AttachedFile]] = None
    # Active writing style: absent/None → the user's saved default; the literal
    # "none" → explicitly no style; otherwise a preset:* id or a custom style id.
    style_id: Optional[str] = None
    # Chat model (registry key from GET /api/models, e.g. "claude-sonnet").
    # Absent/unknown/unavailable → the Gemini default. Selects which per-model
    # Runner handles the turn; history is shared across switches.
    model: Optional[str] = None
    # Legacy single-attachment fields — kept so an older cached frontend build
    # keeps working; normalized into attached_files in the endpoint.
    attached_context: Optional[str] = None
    attached_file_id: Optional[str] = None
    attached_file_name: Optional[str] = None
    attached_mime_type: Optional[str] = None

    def normalized_attachments(self) -> List[AttachedFile]:
        files = list(self.attached_files or [])
        if self.attached_context:
            files.append(AttachedFile(
                text=self.attached_context,
                file_id=self.attached_file_id,
                file_name=self.attached_file_name,
                mime_type=self.attached_mime_type,
            ))
        return files[:_MAX_ATTACHED_FILES]

@router.post("")
async def chat_endpoint(body: ChatRequest, http_request: FastAPIRequest):
    user = getattr(http_request.state, "user", {})
    user_id = user.get("email") or user.get("uid") or body.user_id

    async def sse_generator():
        try:
            try:
                creds_dict = FirestoreService.get_user_credentials(user_id)
            except Exception as fs_err:
                print(f"[chat] Firestore unavailable: {fs_err}", flush=True)
                creds_dict = None

            # Resolve the active writing style BEFORE session get/create so both
            # paths set the same value. The key is (re)assigned on EVERY turn —
            # to the formatted block when a style resolves, to "" otherwise —
            # because session state persists across turns and the {writing_style?}
            # placeholder only skips *absent* keys; a stale block from turn N
            # would otherwise leak into turn N+1 after the user switched it off.
            try:
                from services.style_service import resolve_style, format_style_block
                _style = resolve_style(body.style_id, user_id)
                style_block = format_style_block(_style) if _style else ""
            except Exception as style_err:
                print(f"[chat] style resolution failed: {style_err}", flush=True)
                style_block = ""

            # Active signature note ({signature?} placeholder in every agent).
            # Same per-turn reassignment rule as writing_style: "" when no
            # signature is active, so a deactivated one never leaks into later
            # turns. The note only tells agents a signature exists and is
            # appended by the tools — the body itself is applied server-side.
            try:
                from services.signature_service import resolve_active, format_signature_note
                _sig = resolve_active(user_id)
                signature_note = format_signature_note(_sig) if _sig else ""
            except Exception as sig_err:
                print(f"[chat] signature resolution failed: {sig_err}", flush=True)
                signature_note = ""

            # Selected chat model → which per-model Runner handles this turn.
            # All runners share one session service + app_name, so history and
            # state follow the conversation across model switches.
            from services.model_registry import get_spec
            from agents.runner import get_runner
            spec = get_spec(body.model)
            active_runner = get_runner(spec.key)

            try:
                session = await active_runner.session_service.get_session(
                    app_name="agents",
                    session_id=body.session_id,
                    user_id=user_id,
                )
                if session is None:
                    init_state = {"user_id": user_id, "writing_style": style_block,
                                  "signature": signature_note,
                                  "model_key": spec.key, "model_provider": spec.provider}
                    if creds_dict:
                        init_state["google_credentials"] = creds_dict
                    await active_runner.session_service.create_session(
                        app_name="agents",
                        user_id=user_id,
                        session_id=body.session_id,
                        state=init_state,
                    )
                    # Persist session metadata to Firestore for history page
                    try:
                        folder_id = None
                        if body.folder_id:
                            from services.folder_service import get_folder
                            if get_folder(body.folder_id, user_id):
                                folder_id = body.folder_id
                        now = datetime.now(timezone.utc)
                        FirestoreService.create_session(SessionInDB(
                            session_id=body.session_id,
                            user_id=user_id,
                            title=body.message[:80],
                            folder_id=folder_id,
                            created_at=now,
                            updated_at=now,
                        ))
                    except Exception:
                        pass
                elif creds_dict:
                    session.state["google_credentials"] = creds_dict
                    session.state["user_id"] = user_id

                # Keep only the current turn's attachment in session state, capped
                # at 8000 chars. This dict is serialized to the adk_sessions Firestore
                # doc on every event; an unbounded append would walk toward the 1 MB
                # document limit and eventually break state persistence silently. The
                # attachment is also injected into the message parts below (the path
                # the model actually reads), so session state doesn't need history.
                attachments = body.normalized_attachments()
                if attachments and session:
                    # Text attachments only — image bytes must never land in
                    # session state (serialized to Firestore on every event).
                    session.state["attached_documents"] = [
                        a.text[:_MAX_ATTACHMENT_CHARS]
                        for a in attachments if a.text and not a.image_base64
                    ]

                # Unconditional per-turn (re)assignment — see the style comment
                # above. Goes through update_state (not session.state[...]=):
                # get_session returns a deepcopy, so mutating it here would
                # never reach the session the Runner actually reads.
                if session:
                    await active_runner.session_service.update_state(
                        app_name="agents",
                        user_id=user_id,
                        session_id=body.session_id,
                        delta={"writing_style": style_block, "signature": signature_note,
                               # Per-turn: tools read the provider from state
                               # (image_generate picks Imagen vs OpenAI images).
                               "model_key": spec.key, "model_provider": spec.provider},
                    )
            except Exception as e:
                print(f"Session error: {e}")

            # Persist user message
            try:
                FirestoreService.add_message(MessageInDB(
                    message_id=str(uuid.uuid4()),
                    session_id=body.session_id,
                    role="user",
                    content=body.message,
                    timestamp=datetime.now(timezone.utc),
                ))
            except Exception:
                pass

            # The attached document's text must be part of the actual message sent
            # to the model — session.state["attached_documents"] above is bookkeeping
            # only, nothing reads it back out, so without this the model never sees
            # what the user attached.
            message_parts = []
            image_count = 0
            for att in body.normalized_attachments():
                if att.image_base64:
                    if image_count >= _MAX_IMAGES_PER_MESSAGE:
                        continue
                    try:
                        b64 = att.image_base64
                        if "," in b64[:80] and b64.lstrip().startswith("data:"):
                            b64 = b64.split(",", 1)[1]  # strip data-URL prefix
                        raw = base64.b64decode(b64)
                        if len(raw) > _MAX_IMAGE_INPUT_BYTES:
                            raise ValueError("image exceeds 10 MB")
                        jpeg = _compress_image(raw)
                    except Exception as img_err:
                        print(f"[chat] image attachment skipped: {img_err}", flush=True)
                        continue
                    name = att.file_name or "imagen"
                    message_parts.append(types.Part.from_text(
                        text=f"[Imagen adjunta: {name}]"
                    ))
                    message_parts.append(types.Part.from_bytes(
                        data=jpeg, mime_type="image/jpeg"
                    ))
                    image_count += 1
                    continue
                header = "[Documento adjunto"
                if att.file_name:
                    header += f": {att.file_name}"
                header += "]"
                # Real Drive files carry their ID so agents can act on the file
                # itself (edit the Sheet, extend the Doc/Slides) — synthetic
                # "local:" ids from device uploads are deliberately omitted:
                # those files don't exist in Drive and the ID would only bait
                # the model into calling Drive tools that must fail.
                if att.file_id and not att.file_id.startswith("local:"):
                    header += f"\n[drive_file_id: {att.file_id}"
                    if att.mime_type:
                        header += f" | mimeType: {att.mime_type}"
                    header += "]"
                message_parts.append(types.Part.from_text(
                    text=f"{header}\n{att.text[:_MAX_ATTACHMENT_CHARS]}"
                ))
            message_parts.append(types.Part.from_text(text=body.message))
            # Reply-language note. The UI locale always wins when the frontend
            # sends it (the deterministic note is the mechanism that actually
            # controls reply language — prompt rules alone demonstrably don't).
            # The _is_english sniff survives only as the fallback for older
            # cached frontend builds that don't send `locale` yet.
            locale = (body.locale or "").lower()
            if locale == "en":
                message_parts.append(types.Part.from_text(
                    text="[System note: the user's interface language is ENGLISH — "
                         "your entire reply must be in English, regardless of the "
                         "language of the user's message or of any sources.]"
                ))
            elif locale == "es":
                message_parts.append(types.Part.from_text(
                    text="[Nota de sistema: el idioma de la interfaz del usuario es "
                         "ESPAÑOL — toda tu respuesta debe ir en español, sin importar "
                         "el idioma del mensaje del usuario ni de las fuentes.]"
                ))
            elif _is_english(body.message):
                message_parts.append(types.Part.from_text(
                    text="[System note: the user's message above is in ENGLISH — "
                         "your entire reply must be in English.]"
                ))

            full_response = ""
            last_status = None
            # Vertex quota (429 RESOURCE_EXHAUSTED) blips are frequent on this
            # sandbox project's dynamic shared quota and usually clear within
            # seconds — retry the turn a couple of times before surfacing an
            # error, but only while nothing has streamed to the client yet:
            # retrying after partial output would duplicate text in the UI.
            # Each run_async call re-appends the user message to the session,
            # so a retried turn leaves a duplicated user message in ADK history
            # — an accepted tradeoff for self-healing the common case.
            for attempt in range(1, _MAX_QUOTA_ATTEMPTS + 1):
                try:
                    async for event in active_runner.run_async(
                        new_message=types.Content(role="user", parts=message_parts),
                        session_id=body.session_id,
                        user_id=user_id,
                    ):
                        # Surface which agent/tool is working so the frontend can show a
                        # meaningful "Consultando la base de conocimiento…" style label
                        # instead of a bare blinking cursor. Deduped: only emitted when
                        # the (agent, tool) pair changes.
                        author = getattr(event, "author", None)
                        tool = None
                        try:
                            calls = event.get_function_calls()
                            if calls:
                                tool = calls[0].name
                        except Exception:
                            pass
                        if author != "user" and (author or tool) and (author, tool) != last_status:
                            last_status = (author, tool)
                            yield f"data: {json.dumps({'type': 'status', 'agent': author, 'tool': tool})}\n\n"

                        if getattr(event, "content", None) is not None:
                            text = ""
                            if isinstance(event.content, str):
                                text = event.content
                            elif getattr(event.content, "text", None) is not None:
                                text = event.content.text
                            # parts is a Pydantic field that can be None (seen in
                            # production: transfer/tool-only events) — hasattr is
                            # always True, so guard the value, not the attribute.
                            elif getattr(event.content, "parts", None):
                                for p in event.content.parts:
                                    if p.text is not None:
                                        text += p.text

                            if text:
                                full_response += text
                                yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"

                        if event.is_final_response():
                            yield f"data: {json.dumps({'type': 'final'})}\n\n"
                    break
                except Exception as run_err:
                    if _is_quota_error(run_err) and not full_response and attempt < _MAX_QUOTA_ATTEMPTS:
                        delay = _QUOTA_BACKOFF[attempt - 1] + random.uniform(0, 1.5)
                        print(f"Quota 429 on attempt {attempt}, retrying in {delay:.1f}s", flush=True)
                        await asyncio.sleep(delay)
                        continue
                    raise

            # Persist agent response
            if full_response:
                try:
                    FirestoreService.add_message(MessageInDB(
                        message_id=str(uuid.uuid4()),
                        session_id=body.session_id,
                        role="agent",
                        content=full_response,
                        timestamp=datetime.now(timezone.utc),
                    ))
                except Exception:
                    pass

        except Exception as e:
            # Log the real detail server-side, but never stream raw exception text
            # (Firestore/Google API errors, internal IDs, stack details) to the
            # user — that violates the "no internal details" guardrail. The frontend
            # renders a localized message per event type: `rate_limited` gets an
            # honest "high demand, retry in a few seconds" instead of the generic
            # error that made quota blips look like broken conversations.
            print(f"Error in streaming: {type(e).__name__}: {e}", flush=True)
            event_type = "rate_limited" if _is_quota_error(e) else "error"
            yield f"data: {json.dumps({'type': event_type})}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
