from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, HTTPException, Request
from auth.google_oauth import credentials_from_dict, credentials_to_dict
from services.firestore import FirestoreService, db
from services.email.gmail_provider import GmailProvider
from services.email.followup_service import generate_followup_draft
from services.email.triage_service import classify_priority

router = APIRouter(prefix="/api/email", tags=["email"])


def _local_midnight_epoch(tz_name: Optional[str]) -> int:
    """Returns the Unix epoch second for local midnight today in tz_name.

    Falls back to UTC on a missing/invalid timezone name. Using an epoch
    timestamp (rather than a YYYY/MM/DD string) with Gmail's after: operator
    avoids any ambiguity about which timezone the date string would be
    interpreted in — confirmed empirically that Gmail search accepts and
    correctly filters on epoch-second values.
    """
    try:
        tz = ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    midnight_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight_local.timestamp())


def _credentials_for_user(user_id: str):
    creds_dict = FirestoreService.get_user_credentials(user_id)
    if not creds_dict:
        return None
    creds = credentials_from_dict(creds_dict)
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request as GRequest
            creds.refresh(GRequest())
            FirestoreService.update_credentials(user_id, credentials_to_dict(creds))
        except Exception as e:
            print(f"[email summary] token refresh failed: {e}")
    return creds


def _dedupe_by_thread(messages: list) -> list:
    seen = set()
    unique = []
    for m in messages:
        tid = m.get("thread_id")
        if tid in seen:
            continue
        seen.add(tid)
        unique.append(m)
    return unique


@router.get("/summary")
def get_email_summary(request: Request, tz: Optional[str] = None):
    user = getattr(request.state, "user", {})
    user_id = user.get("email") or user.get("uid") or "sandbox-user"
    creds = _credentials_for_user(user_id)

    warnings: list = []

    # Epoch timestamp, not a YYYY/MM/DD string, so "today" always means the
    # executive's actual local calendar day — wherever they're logged in from
    # right now — regardless of server/UTC time. See _local_midnight_epoch.
    midnight_epoch = _local_midnight_epoch(tz)

    try:
        inbox_today_raw = GmailProvider.search_threads(f"in:inbox after:{midnight_epoch}", max_results=50, credentials=creds)
        inbox_today = _dedupe_by_thread(inbox_today_raw)
    except Exception as e:
        print(f"[email summary] inbox fetch failed: {e}")
        inbox_today = []
        warnings.append("inbox")

    if inbox_today:
        try:
            priorities = classify_priority(inbox_today)
            for item, priority in zip(inbox_today, priorities):
                item["priority"] = priority
        except Exception as e:
            print(f"[email summary] priority classification failed: {e}")

    try:
        criticos = len(_dedupe_by_thread(
            GmailProvider.search_threads(f"in:inbox is:important after:{midnight_epoch}", max_results=50, credentials=creds)
        ))
    except Exception as e:
        print(f"[email summary] criticos fetch failed: {e}")
        criticos = 0
        warnings.append("criticos")

    try:
        pendientes = len(_dedupe_by_thread(
            GmailProvider.search_threads(f"in:inbox is:unread after:{midnight_epoch}", max_results=50, credentials=creds)
        ))
    except Exception as e:
        print(f"[email summary] pendientes fetch failed: {e}")
        pendientes = 0
        warnings.append("pendientes")

    try:
        tracked_docs = db.collection("email_tracking").where(
            "user_id", "==", user_id
        ).where("status", "==", "waiting").stream()
        tracked = [{"tracking_id": doc.id, **doc.to_dict()} for doc in tracked_docs]
        for t in tracked:
            if "deadline" in t and hasattr(t["deadline"], "isoformat"):
                t["deadline"] = t["deadline"].isoformat()
            if "created_at" in t and hasattr(t["created_at"], "isoformat"):
                t["created_at"] = t["created_at"].isoformat()
            # Self-heal legacy records tracked before subject/to were captured
            # at creation time — never show the raw Gmail message_id to the user.
            if not t.get("subject") and t.get("message_id"):
                try:
                    headers = GmailProvider.get_message_headers(t["message_id"], credentials=creds)
                    t["subject"] = headers.get("subject", "")
                    t["to"] = headers.get("to", "")
                except Exception as enrich_err:
                    print(f"[email summary] tracked subject lookup failed: {enrich_err}")
    except Exception as e:
        print(f"[email summary] tracking fetch failed: {e}")
        tracked = []
        warnings.append("tracked")

    return {
        "status": "success",
        "inbox_today": inbox_today,
        "tracked": tracked,
        "indicators": {
            "bandeja": len(inbox_today),
            "criticos": criticos,
            "pendientes": pendientes,
            "seguimiento": len(tracked),
        },
        "warnings": warnings,
    }


@router.post("/tracking/{tracking_id}/generate-followup")
def generate_followup(tracking_id: str, request: Request):
    user = getattr(request.state, "user", {})
    user_id = user.get("email") or user.get("uid") or "sandbox-user"
    creds = _credentials_for_user(user_id)
    try:
        result = generate_followup_draft(tracking_id, credentials=creds)
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Follow-up generation failed: {e}")
