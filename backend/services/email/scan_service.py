"""Incremental email scan engine for Correo Ejecutivo v2.

Runs when the executive opens/refreshes the dashboard (decision: no scheduled
scan job). Lists inbox+sent threads in the rolling window, diffs against
stored state by Gmail historyId (unchanged threads cost zero extra API calls),
batch-fetches and re-analyzes only new/changed threads, applies the state
transitions of the functional spec (docs/propuesta-email-ejecutivo-v2.md §4.2),
reconciles manual email_tracking records, and returns the assembled dashboard
payload.

Failure model mirrors news_service: every sub-failure appends a warning and
degrades to stored state — a scan never 500s the dashboard.
"""

import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from config import settings
from services.email import analysis_service, thread_store
from services.email.gmail_provider import GmailProvider

_DAY_MS = 86_400_000

_PRIORITY_RANK = {"BAJO": 0, "MEDIO": 1, "ALTO": 2, "CRITICO": 3}


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# pure helpers (unit-testable without Gmail/Firestore)

def _compute_thread_fields(thread: Dict[str, Any]) -> Dict[str, Any]:
    """Derives direction/timestamps/display fields from a parsed Gmail thread."""
    messages = sorted(thread.get("messages", []), key=lambda m: m.get("internal_date", 0))
    if not messages:
        return {}
    last = messages[-1]
    outbound = [m for m in messages if "SENT" in (m.get("label_ids") or [])]
    inbound = [m for m in messages if "SENT" not in (m.get("label_ids") or [])]
    last_from_me = "SENT" in (last.get("label_ids") or [])
    # Display sender/recipient: last inbound's From, last outbound's To.
    from_display = inbound[-1].get("from", "") if inbound else last.get("from", "")
    to_display = outbound[-1].get("to", "") if outbound else last.get("to", "")
    return {
        "thread_id": thread.get("id", ""),
        "subject": last.get("subject", "") or (messages[0].get("subject", "")),
        "from": from_display,
        "to": to_display,
        "snippet": last.get("snippet", "") or thread.get("snippet", ""),
        "date": last.get("date", ""),
        "message_count": len(messages),
        "is_sent_thread": last_from_me,
        "last_message_from_me": last_from_me,
        "last_outbound_at": outbound[-1].get("internal_date", 0) if outbound else None,
        "last_inbound_at": inbound[-1].get("internal_date", 0) if inbound else None,
        "last_message_internal_date": last.get("internal_date", 0),
        "last_analyzed_message_id": last.get("id", ""),
        "gmail_history_id": str(thread.get("history_id", "")),
        "last_rfc822_message_id": last.get("rfc822_message_id", ""),
        "last_references": last.get("references", ""),
    }


def _build_excerpt(thread: Dict[str, Any]) -> str:
    """Last 2 messages, oldest first, labeled by direction — the model needs
    direction to judge requiere_accion correctly."""
    messages = sorted(thread.get("messages", []), key=lambda m: m.get("internal_date", 0))
    parts = []
    for m in messages[-2:]:
        who = "[EJECUTIVO]" if "SENT" in (m.get("label_ids") or []) else "[REMITENTE]"
        text = (m.get("body") or m.get("snippet") or "").strip()[:1200]
        parts.append(f"{who} {text}")
    return "\n".join(parts)


def _apply_transitions(prev: Optional[Dict[str, Any]], fields: Dict[str, Any],
                       followup_days: int, now_ms: int) -> Dict[str, Any]:
    """State transitions for a NEW or CHANGED thread (spec §4.2/§4.7).

    Returns the merged doc (prev fields preserved where the spec says user
    state wins). Re-open/reclassify rules that depend on the fresh analysis
    (requiere_accion) are finalized in _apply_analysis.
    """
    doc = dict(prev) if prev else {}
    had_new_message = bool(prev) and fields.get("last_message_internal_date", 0) > (
        prev.get("last_message_internal_date") or 0
    )
    doc.update(fields)

    if not prev:
        # First time this thread enters state.
        doc["estado_gestion"] = "gestionado" if fields.get("last_message_from_me") else "nuevo"
        doc["prioridad"] = "MEDIO"
        doc["prioridad_source"] = "ai"
        doc["user_priority"] = None
        doc["ai_reescalated"] = False
        doc["requiere_accion"] = False
        doc["accion_tipo"] = "informativo"
        doc["postponed_until"] = None
        doc.setdefault("tracking_id", None)
        doc.setdefault("followup_draft_id", None)
        doc["_reopened_by_inbound"] = False
    elif had_new_message:
        if fields.get("last_message_from_me"):
            # Own reply — from the dashboard, the chat, or Gmail itself —
            # marks the thread managed (decision 8). Reads never do.
            doc["estado_gestion"] = "gestionado"
            doc["_reopened_by_inbound"] = False
        else:
            # New inbound. Waiting threads become respondido; whether a
            # gestionado/respondido/resuelto thread reopens to nuevo depends
            # on the fresh analysis (decision 9) — flagged for _apply_analysis.
            if prev.get("esperando_respuesta"):
                doc["estado_gestion"] = "respondido"
            doc["_reopened_by_inbound"] = prev.get("estado_gestion") in (
                "gestionado", "respondido", "resuelto", "pospuesto"
            )
    else:
        doc["_reopened_by_inbound"] = False

    doc["esperando_respuesta"] = _waiting_reply(doc, followup_days, now_ms)
    return doc


def _waiting_reply(doc: Dict[str, Any], followup_days: int, now_ms: int) -> bool:
    """A sent thread is awaiting reply when the executive spoke last, the
    follow-up window elapsed, and the user hasn't resolved/postponed it."""
    if not doc.get("last_message_from_me"):
        return False
    if doc.get("estado_gestion") in ("resuelto",):
        return False
    postponed = doc.get("postponed_until")
    if doc.get("estado_gestion") == "pospuesto" and postponed and now_ms < postponed:
        return False
    last_out = doc.get("last_outbound_at") or 0
    threshold = followup_days * _DAY_MS
    # Manually tracked threads are follow-up candidates immediately.
    if doc.get("tracking_id"):
        return True
    return bool(last_out) and (now_ms - last_out) > threshold


def _apply_analysis(doc: Dict[str, Any], analysis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merges a fresh analysis into the doc, honoring the user-priority floor
    (decision 4: AI may raise, never lower) and the reopen rule (decision 9)."""
    reopened_flag = doc.pop("_reopened_by_inbound", False)
    if analysis is None:
        # Failed chunk — keep previous facets (or the defaults set above).
        return doc

    doc["resumen"] = analysis["resumen"]
    doc["accion_sugerida"] = analysis["accion_sugerida"]
    doc["fecha_limite"] = analysis["fecha_limite"]
    doc["requiere_accion"] = analysis["requiere_accion"]
    doc["accion_tipo"] = analysis["accion_tipo"]

    ai_priority = analysis["prioridad"]
    if doc.get("prioridad_source") == "user" and doc.get("user_priority"):
        user_rank = _PRIORITY_RANK.get(doc["user_priority"], 1)
        ai_rank = _PRIORITY_RANK.get(ai_priority, 1)
        if ai_rank > user_rank:
            doc["prioridad"] = ai_priority
            doc["ai_reescalated"] = True
        else:
            doc["prioridad"] = doc["user_priority"]
            doc["ai_reescalated"] = False
    else:
        doc["prioridad"] = ai_priority
        doc["prioridad_source"] = "ai"
        doc["ai_reescalated"] = False

    # Reopen: a managed/answered/resolved/postponed thread that received a new
    # inbound message returns to "nuevo" only when it carries a real request.
    if reopened_flag and analysis["requiere_accion"]:
        doc["estado_gestion"] = "nuevo"
        doc["postponed_until"] = None
    return doc


def _maintenance_pass(docs: List[Dict[str, Any]], followup_days: int,
                      now_ms: int) -> List[Dict[str, Any]]:
    """Time-based flag refresh for ALL in-window docs — unchanged threads still
    cross follow-up/postpone thresholds as time passes. Returns docs whose
    flags changed (to persist)."""
    changed = []
    for doc in docs:
        updates: Dict[str, Any] = {}
        if (doc.get("estado_gestion") == "pospuesto"
                and doc.get("postponed_until") and now_ms >= doc["postponed_until"]):
            updates["estado_gestion"] = "gestionado"
            updates["postponed_until"] = None
            doc.update(updates)
        waiting = _waiting_reply(doc, followup_days, now_ms)
        if waiting != bool(doc.get("esperando_respuesta")):
            updates["esperando_respuesta"] = waiting
            doc["esperando_respuesta"] = waiting
        if updates:
            changed.append({"thread_id": doc["thread_id"], **updates})
    return changed


def compute_indicators(docs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Server-side view counts — MUST stay in lockstep with the frontend's view
    rules. Strict precedence Critical > Pending (decision 3); Inbox includes
    criticals (a new critical must never be hidden from the default view)."""
    bandeja = criticos = pendientes = seguimiento = 0
    for d in docs:
        estado = d.get("estado_gestion")
        if estado == "nuevo":
            bandeja += 1
        if d.get("prioridad") == "CRITICO" and estado != "resuelto":
            criticos += 1
        elif d.get("requiere_accion") and estado != "resuelto":
            pendientes += 1
        if d.get("esperando_respuesta") and estado != "pospuesto":
            seguimiento += 1
    return {"bandeja": bandeja, "criticos": criticos,
            "pendientes": pendientes, "seguimiento": seguimiento}


def _serialize(doc: Dict[str, Any], now_ms: int) -> Dict[str, Any]:
    out = {k: v for k, v in doc.items() if not k.startswith("_")}
    last_out = out.get("last_outbound_at")
    out["days_without_reply"] = (
        max(0, (now_ms - last_out) // _DAY_MS)
        if out.get("esperando_respuesta") and last_out else None
    )
    return out


def assemble(user_id: str, user_settings: Dict[str, Any],
             warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    """Dashboard payload from stored state only — no Gmail/Gemini calls.
    Persists any time-based flag changes it detects (postpone expiry, new
    follow-up candidates)."""
    now_ms = _now_ms()
    window_start = now_ms - user_settings["window_days"] * _DAY_MS
    docs = thread_store.get_threads(user_id, window_start)
    flag_updates = _maintenance_pass(docs, user_settings["followup_days"], now_ms)
    if flag_updates:
        thread_store.upsert_threads(user_id, flag_updates)
    return {
        "threads": [_serialize(d, now_ms) for d in docs],
        "indicators": compute_indicators(docs),
        "settings": user_settings,
        "warnings": warnings or [],
    }


# ---------------------------------------------------------------------------
# the scan

def run_scan(user_id: str, credentials,
             progress: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    """Incremental scan → assembled dashboard payload. Never raises for
    sub-failures; each one lands in warnings[]."""
    emit = progress or (lambda evt: None)
    warnings: List[str] = []
    user_settings = thread_store.get_email_settings(user_id)
    now_ms = _now_ms()

    # Cooldown: a second open/refresh within the window serves stored state.
    meta = thread_store.get_scan_meta(user_id)
    last_scan = meta.get("last_scan_at")
    if isinstance(last_scan, (int, float)) and (
            now_ms - last_scan < settings.EMAIL_SCAN_COOLDOWN_SECONDS * 1000):
        return assemble(user_id, user_settings)

    window_days = user_settings["window_days"]
    followup_days = user_settings["followup_days"]
    window_start_ms = now_ms - window_days * _DAY_MS
    after_epoch_s = window_start_ms // 1000

    # 1. List thread refs (2 paginated queries, no detail fetches).
    emit({"type": "progress", "phase": "listing"})
    refs: Dict[str, Dict[str, Any]] = {}
    try:
        cap = settings.EMAIL_SCAN_MAX_THREADS
        for query in (f"in:inbox after:{after_epoch_s}", f"in:sent after:{after_epoch_s}"):
            for ref in GmailProvider.list_thread_refs(query, max_results=cap,
                                                      credentials=credentials):
                refs[ref["id"]] = ref
        if len(refs) > cap:
            refs = dict(list(refs.items())[:cap])
    except Exception as e:
        print(f"[scan_service] gmail listing failed: {e}")
        warnings.append("gmail_list")
        return assemble(user_id, user_settings, warnings)

    # 2. Diff against stored state by historyId.
    stored = {d["thread_id"]: d for d in thread_store.get_threads(user_id, window_start_ms)}
    to_fetch = [
        tid for tid, ref in refs.items()
        if tid not in stored or str(stored[tid].get("gmail_history_id", "")) != str(ref.get("history_id", ""))
    ]
    emit({"type": "progress", "phase": "fetching", "total": len(to_fetch)})

    updated_docs: List[Dict[str, Any]] = []
    if to_fetch:
        # 3. Batch-fetch changed/new threads.
        try:
            batch = GmailProvider.get_threads_batch(to_fetch, credentials=credentials)
            if batch["failed"]:
                warnings.append("gmail_fetch_partial")
        except Exception as e:
            print(f"[scan_service] batch fetch failed: {e}")
            warnings.append("gmail_fetch")
            batch = {"threads": {}, "failed": to_fetch}

        # 4. Transitions + analysis for each fetched thread.
        analysis_inputs, docs_pending = [], []
        for tid, thread in batch["threads"].items():
            fields = _compute_thread_fields(thread)
            if not fields:
                continue
            doc = _apply_transitions(stored.get(tid), fields, followup_days, now_ms)
            docs_pending.append(doc)
            analysis_inputs.append({
                "subject": doc.get("subject", ""),
                "from": doc.get("from", ""),
                "to": doc.get("to", ""),
                "is_sent_thread": doc.get("is_sent_thread", False),
                "excerpt": _build_excerpt(thread),
            })

        emit({"type": "progress", "phase": "analyzing", "total": len(docs_pending)})
        analyses = analysis_service.analyze_threads(analysis_inputs)
        if any(a is None for a in analyses):
            warnings.append("analysis")
        for doc, analysis in zip(docs_pending, analyses):
            updated_docs.append(_apply_analysis(doc, analysis))
        doc_map = {d["thread_id"]: d for d in updated_docs}
        stored.update(doc_map)

    # 5. Reconcile manual tracking records (chat "haz seguimiento a este correo").
    try:
        _reconcile_tracking(user_id, stored, credentials)
    except Exception as e:
        print(f"[scan_service] tracking reconcile failed: {e}")
        warnings.append("tracking")

    # 6. Persist changed docs + scan meta.
    if updated_docs:
        thread_store.upsert_threads(user_id, updated_docs)
    thread_store.update_scan_meta(user_id, {
        "last_scan_at": now_ms,
        "last_scan_thread_count": len(refs),
    })

    result = assemble(user_id, user_settings, warnings)
    result["analyzed_count"] = len(updated_docs)
    return result


def _reconcile_tracking(user_id: str, stored: Dict[str, Dict[str, Any]],
                        credentials) -> None:
    """Links manual email_tracking records to thread state and detects replies
    to tracked sends (tracking status → responded)."""
    for t in thread_store.get_tracked(user_id, ["waiting", "followup_drafted"]):
        thread_id = t.get("thread_id")
        if not thread_id and t.get("message_id"):
            # Legacy record from before thread_id was captured — self-heal.
            try:
                headers = GmailProvider.get_message_headers(
                    t["message_id"], credentials=credentials)
                thread_id = headers.get("thread_id", "")
                if thread_id:
                    thread_store.update_tracking(t["tracking_id"], {"thread_id": thread_id})
            except Exception as e:
                print(f"[scan_service] tracking header lookup failed: {e}")
                continue
        doc = stored.get(thread_id)
        if not doc:
            continue
        created = t.get("created_at")
        created_ms = int(created.timestamp() * 1000) if hasattr(created, "timestamp") else 0
        if doc.get("last_inbound_at") and doc["last_inbound_at"] > created_ms:
            # The recipient replied after the tracked send.
            thread_store.update_tracking(t["tracking_id"], {"status": "responded"})
            doc["esperando_respuesta"] = False
            if doc.get("estado_gestion") not in ("resuelto",):
                doc["estado_gestion"] = "respondido"
        else:
            doc["tracking_id"] = t["tracking_id"]
            if t.get("followup_draft_id"):
                doc["followup_draft_id"] = t["followup_draft_id"]
            if doc.get("estado_gestion") not in ("resuelto", "pospuesto"):
                doc["esperando_respuesta"] = True
        thread_store.upsert_threads(user_id, [doc])
