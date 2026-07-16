import base64
import html as _html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional

from googleapiclient.discovery import build
import google.auth

_GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def get_gmail_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default(scopes=_GMAIL_SCOPES)
    return build('gmail', 'v1', credentials=credentials)


def _header(headers: List[Dict[str, str]], name: str) -> str:
    """Return the value of a header (case-insensitive) or empty string."""
    name = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name:
            return h.get("value", "")
    return ""


def _decode_b64(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return ""


class HistoryExpired(Exception):
    """Gmail returned 404 for a startHistoryId that is too old — the caller
    must fall back to a full window scan instead of an incremental one."""


class GmailProvider:
    @staticmethod
    def _extract_body(payload: Dict[str, Any]) -> str:
        """Recursively extract the text/plain body from a MIME payload."""
        if not payload:
            return ""

        mime_type = payload.get("mimeType", "")
        body = payload.get("body", {})

        # Leaf node with text/plain content.
        if mime_type == "text/plain" and body.get("data"):
            return _decode_b64(body["data"])

        # Recurse into parts, preferring text/plain.
        parts = payload.get("parts", [])
        if parts:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    text = GmailProvider._extract_body(part)
                    if text:
                        return text
            # Fall back to recursing into any part (e.g. nested multipart).
            for part in parts:
                text = GmailProvider._extract_body(part)
                if text:
                    return text

        # Last resort: a single-part HTML body or other text.
        if body.get("data"):
            return _decode_b64(body["data"])

        return ""

    @staticmethod
    def list_threads(max_results: int = 50, folder: str = "inbox", credentials=None) -> List[Dict[str, Any]]:
        service = get_gmail_service(credentials)
        label = (folder or "inbox").upper()
        result = service.users().threads().list(
            userId="me", labelIds=[label], maxResults=max_results
        ).execute()

        threads = []
        for t in result.get("threads", []):
            detail = service.users().threads().get(
                userId="me", id=t["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()
            messages = detail.get("messages", [])
            headers = messages[0].get("payload", {}).get("headers", []) if messages else []
            threads.append({
                "id": t["id"],
                "snippet": detail.get("snippet", t.get("snippet", "")),
                "subject": _header(headers, "Subject"),
                "from": _header(headers, "From"),
                "date": _header(headers, "Date"),
                "message_count": len(messages),
            })
        return threads

    @staticmethod
    def _parse_message(msg: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes a full-format Gmail message resource into the dict shape
        the rest of the platform consumes. `label_ids`/`internal_date` drive
        direction detection and ordering in the v2 scan engine;
        `rfc822_message_id`/`references` let reply drafts thread correctly for
        external recipients (threadId alone only threads in the sender's own
        mailbox)."""
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        internal = msg.get("internalDate")
        return {
            "id": msg.get("id"),
            "subject": _header(headers, "Subject"),
            "from": _header(headers, "From"),
            "to": _header(headers, "To"),
            "date": _header(headers, "Date"),
            "snippet": msg.get("snippet", ""),
            "body": GmailProvider._extract_body(payload),
            "label_ids": msg.get("labelIds", []),
            "internal_date": int(internal) if internal else 0,
            "rfc822_message_id": _header(headers, "Message-ID"),
            "references": _header(headers, "References"),
        }

    @staticmethod
    def _parse_thread(thread: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": thread.get("id", ""),
            "history_id": thread.get("historyId", ""),
            "snippet": thread.get("snippet", ""),
            "messages": [GmailProvider._parse_message(m) for m in thread.get("messages", [])],
        }

    @staticmethod
    def get_thread(thread_id: str, credentials=None) -> Dict[str, Any]:
        service = get_gmail_service(credentials)
        thread = service.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()
        parsed = GmailProvider._parse_thread(thread)
        parsed["id"] = parsed["id"] or thread_id
        return parsed

    @staticmethod
    def list_thread_refs(query: str, max_results: int = 150, credentials=None) -> List[Dict[str, Any]]:
        """Lists thread references matching a Gmail query, paginated.

        Uses threads().list(q=...) — one call per page of up to 100 threads,
        no per-thread detail fetch. Each ref carries `history_id`, which changes
        whenever the thread changes: the scan engine compares it against stored
        state to skip unchanged threads at zero additional API cost.
        """
        service = get_gmail_service(credentials)
        refs: List[Dict[str, Any]] = []
        token = None
        while len(refs) < max_results:
            resp = service.users().threads().list(
                userId="me", q=query,
                maxResults=min(100, max_results - len(refs)),
                pageToken=token,
            ).execute()
            for t in resp.get("threads", []):
                refs.append({
                    "id": t["id"],
                    "history_id": t.get("historyId", ""),
                    "snippet": t.get("snippet", ""),
                })
            token = resp.get("nextPageToken")
            if not token:
                break
        return refs[:max_results]

    @staticmethod
    def get_threads_batch(thread_ids: List[str], credentials=None) -> Dict[str, Any]:
        """Fetches full threads in batched HTTP requests (25 per batch).

        Returns {"threads": {thread_id: parsed_thread}, "failed": [thread_id]}.
        A failing item is omitted and reported — one bad thread never fails the
        whole batch (mirrors the per-source isolation in news_service).
        """
        service = get_gmail_service(credentials)
        results: Dict[str, Dict[str, Any]] = {}
        failed: List[str] = []

        def _collect(request_id, response, exception):
            if exception is not None:
                print(f"[gmail_provider] batch get failed for thread {request_id}: {exception}")
                failed.append(request_id)
                return
            results[request_id] = GmailProvider._parse_thread(response)

        for start in range(0, len(thread_ids), 25):
            chunk = thread_ids[start:start + 25]
            batch = service.new_batch_http_request(callback=_collect)
            for tid in chunk:
                batch.add(
                    service.users().threads().get(userId="me", id=tid, format="full"),
                    request_id=tid,
                )
            batch.execute()

        return {"threads": results, "failed": failed}

    @staticmethod
    def search_threads(query: str, max_results: int = 10, credentials=None) -> List[Dict[str, Any]]:
        service = get_gmail_service(credentials)
        result = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()

        messages = []
        for m in result.get("messages", []):
            detail = service.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()
            headers = detail.get("payload", {}).get("headers", [])
            messages.append({
                "id": detail.get("id"),
                "thread_id": detail.get("threadId"),
                "snippet": detail.get("snippet", ""),
                "subject": _header(headers, "Subject"),
                "from": _header(headers, "From"),
                "date": _header(headers, "Date"),
            })
        return messages

    @staticmethod
    def get_message_headers(message_id: str, credentials=None) -> Dict[str, str]:
        """Fetches Subject/To/From/threadId for a message without downloading the body.

        Used to enrich tracked-email records with descriptive info (subject, recipient)
        instead of only ever storing the raw Gmail message_id.
        """
        service = get_gmail_service(credentials)
        msg = service.users().messages().get(
            userId="me", id=message_id, format="metadata",
            metadataHeaders=["Subject", "To", "From"]
        ).execute()
        headers = msg.get("payload", {}).get("headers", [])
        return {
            "subject": _header(headers, "Subject"),
            "to": _header(headers, "To"),
            "from": _header(headers, "From"),
            "thread_id": msg.get("threadId", ""),
            "snippet": msg.get("snippet", ""),
        }

    @staticmethod
    def _build_raw_message(to: str, subject: str, body: str,
                           signature: Optional[Dict[str, Any]] = None,
                           in_reply_to: Optional[str] = None,
                           references: Optional[str] = None) -> str:
        """Builds the base64url-encoded RFC 822 message shared by draft
        create/update and direct sends. When `signature` (a `signatures`
        Firestore dict, see services/signature_service.py) is provided, the
        message is multipart/alternative — plain text with the signature text
        appended, plus an HTML part where the signature can include its logo
        image. `in_reply_to`/`references` (RFC 822 Message-ID values) make a
        reply thread correctly in the RECIPIENT's mailbox — threadId alone only
        threads it in the sender's own."""
        if signature:
            from services.signature_service import build_html_signature
            plain = body.rstrip() + "\n\n" + (signature.get("content") or "")
            html_body = _html.escape(body.rstrip()).replace("\n", "<br>")
            html_full = (
                f'<div>{html_body}<br><br>{build_html_signature(signature)}</div>'
            )
            message = MIMEMultipart("alternative")
            # Order matters: last part is preferred by clients — HTML wins.
            message.attach(MIMEText(plain, "plain"))
            message.attach(MIMEText(html_full, "html"))
        else:
            message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = (references or in_reply_to)
        return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    @staticmethod
    def create_draft(to: str, subject: str, body: str, thread_id: Optional[str] = None,
                     credentials=None, signature: Optional[Dict[str, Any]] = None,
                     in_reply_to: Optional[str] = None,
                     references: Optional[str] = None) -> str:
        service = get_gmail_service(credentials)
        raw = GmailProvider._build_raw_message(to, subject, body, signature,
                                               in_reply_to, references)
        draft_body: Dict[str, Any] = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        draft = service.users().drafts().create(userId="me", body=draft_body).execute()
        return draft["id"]

    @staticmethod
    def update_draft(draft_id: str, to: str, subject: str, body: str,
                     thread_id: Optional[str] = None, credentials=None,
                     signature: Optional[Dict[str, Any]] = None,
                     in_reply_to: Optional[str] = None,
                     references: Optional[str] = None) -> str:
        """Replaces a draft's content in place (drafts().update). The edited
        text — not the originally generated one — is what a later send_draft
        actually sends."""
        service = get_gmail_service(credentials)
        raw = GmailProvider._build_raw_message(to, subject, body, signature,
                                               in_reply_to, references)
        draft_body: Dict[str, Any] = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        draft = service.users().drafts().update(
            userId="me", id=draft_id, body=draft_body
        ).execute()
        return draft["id"]

    @staticmethod
    def delete_draft(draft_id: str, credentials=None) -> None:
        service = get_gmail_service(credentials)
        service.users().drafts().delete(userId="me", id=draft_id).execute()

    @staticmethod
    def send_draft(draft_id: str, credentials=None) -> str:
        service = get_gmail_service(credentials)
        sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
        return sent.get("id")

    @staticmethod
    def get_draft(draft_id: str, credentials=None) -> Dict[str, Any]:
        service = get_gmail_service(credentials)
        draft = service.users().drafts().get(userId="me", id=draft_id, format="full").execute()
        message = draft.get("message", {})
        payload = message.get("payload", {})
        headers = payload.get("headers", [])
        return {
            "id": draft.get("id"),
            "message_id": message.get("id"),
            "thread_id": message.get("threadId"),
            "subject": _header(headers, "Subject"),
            "to": _header(headers, "To"),
            "body": GmailProvider._extract_body(payload),
        }
