"""Machine-invoked endpoints (Phase 3): Gmail push, watch renewal, weekly digest.

Prefix /hooks is deliberately OUTSIDE auth_middleware's _AUTHENTICATED_PREFIXES
— these callers are Pub/Sub push and Cloud Scheduler, not browsers with user
JWTs. Auth is Google-signed OIDC verified in-app: the token's audience must be
this backend and its service-account email must match HOOKS_OIDC_SERVICE_ACCOUNT.
With that setting empty, every /hooks route 404s (feature off).

The push handler must ALWAYS return 200 quickly — a non-2xx makes Pub/Sub
redeliver in a retry storm. Idempotency: the stored gmail_watch.history_id
only ever moves forward (monotonic compare), so redeliveries are no-ops.
"""

import base64
import json

from fastapi import APIRouter, HTTPException, Request

from config import settings
from services.email import digest_service, scan_service, thread_store
from services.email.gmail_provider import GmailProvider, HistoryExpired
from services.firestore import db

router = APIRouter(prefix="/hooks", tags=["hooks"])


def _verify_oidc(request: Request) -> None:
    if not settings.HOOKS_OIDC_SERVICE_ACCOUNT:
        raise HTTPException(status_code=404)
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=403, detail="Missing OIDC token")
    token = auth.split(" ", 1)[1]
    try:
        from google.auth.transport.requests import Request as GRequest
        from google.oauth2 import id_token as id_token_lib
        claims = id_token_lib.verify_oauth2_token(
            token, GRequest(), audience=settings.HOOKS_OIDC_AUDIENCE)
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid OIDC token")
    if claims.get("email") != settings.HOOKS_OIDC_SERVICE_ACCOUNT or not claims.get("email_verified"):
        raise HTTPException(status_code=403, detail="Unauthorized service account")


def _users_with_credentials():
    """(user_id, creds) pairs for every user with stored Google credentials."""
    from routers.email import _credentials_for_user
    for doc in db.collection("users").stream():
        data = doc.to_dict() or {}
        if not data.get("google_credentials"):
            continue
        creds = _credentials_for_user(doc.id)
        if creds:
            yield doc.id, creds


@router.post("/gmail-push")
async def gmail_push(request: Request):
    _verify_oidc(request)
    try:
        envelope = await request.json()
        data = json.loads(base64.b64decode(
            envelope.get("message", {}).get("data", "")).decode("utf-8"))
        email = data.get("emailAddress", "")
        new_history_id = int(data.get("historyId", 0))
    except Exception as e:
        print(f"[hooks] undecodable push message: {e}")
        return {"status": "ignored"}

    try:
        meta = thread_store.get_watch_meta(email)
        stored_history = int(meta.get("history_id") or 0)
        if not stored_history:
            return {"status": "no_watch_state"}
        if new_history_id and new_history_id <= stored_history:
            return {"status": "stale"}  # redelivery / out-of-order — idempotent no-op

        from routers.email import _credentials_for_user
        creds = _credentials_for_user(email)
        if not creds:
            return {"status": "no_credentials"}

        try:
            history = GmailProvider.list_history(str(stored_history), credentials=creds)
        except HistoryExpired:
            # Too old — flag a full scan for the next dashboard open.
            scan_meta = thread_store.get_scan_meta(email)
            scan_meta["needs_full_scan"] = True
            thread_store.update_scan_meta(email, scan_meta)
            thread_store.update_watch_meta(email, {**meta, "history_id": str(new_history_id)})
            return {"status": "history_expired"}

        thread_ids = list(history["thread_ids"])
        if thread_ids:
            user_settings = thread_store.get_email_settings(email)
            import time
            now_ms = int(time.time() * 1000)
            stored = {}
            for tid in thread_ids:
                prev = thread_store.get_thread(email, tid)
                if prev:
                    stored[tid] = prev
            updated = scan_service.process_thread_ids(
                email, thread_ids, stored, user_settings["followup_days"],
                now_ms, creds)
            if updated:
                thread_store.upsert_threads(email, updated)

        latest = max(int(history["history_id"] or 0), new_history_id, stored_history)
        thread_store.update_watch_meta(email, {**meta, "history_id": str(latest)})
        return {"status": "success", "threads_updated": len(thread_ids)}
    except Exception as e:
        # Never propagate — a 500 here triggers Pub/Sub retry storms.
        print(f"[hooks] gmail-push processing failed for {email}: {e}")
        return {"status": "error_logged"}


@router.post("/watch-renew")
async def watch_renew(request: Request):
    _verify_oidc(request)
    renewed, skipped, failed = 0, 0, 0
    for user_id, creds in _users_with_credentials():
        try:
            import time
            meta = thread_store.get_watch_meta(user_id)
            if not meta:
                skipped += 1  # user never scanned — watch starts at first scan
                continue
            if (meta.get("expiration_ms") or 0) - time.time() * 1000 > 48 * 3_600_000:
                skipped += 1
                continue
            result = GmailProvider.watch(settings.GMAIL_PUSH_TOPIC, credentials=creds)
            thread_store.update_watch_meta(user_id, {
                **result, "registered_at": int(time.time() * 1000)})
            renewed += 1
        except Exception as e:
            print(f"[hooks] watch renewal failed for {user_id}: {e}")
            failed += 1
    return {"status": "success", "renewed": renewed, "skipped": skipped, "failed": failed}


@router.post("/digest")
async def weekly_digest(request: Request):
    _verify_oidc(request)
    generated, emailed, failed = 0, 0, 0
    for user_id, creds in _users_with_credentials():
        try:
            digest = digest_service.generate_digest(user_id, credentials=creds)
            generated += 1
            if digest.get("emailed"):
                emailed += 1
        except Exception as e:
            print(f"[hooks] digest failed for {user_id}: {e}")
            failed += 1
    return {"status": "success", "generated": generated, "emailed": emailed, "failed": failed}
