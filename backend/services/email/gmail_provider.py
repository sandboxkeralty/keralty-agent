import base64
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
    def get_thread(thread_id: str, credentials=None) -> Dict[str, Any]:
        service = get_gmail_service(credentials)
        thread = service.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()

        messages = []
        for msg in thread.get("messages", []):
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            messages.append({
                "id": msg.get("id"),
                "subject": _header(headers, "Subject"),
                "from": _header(headers, "From"),
                "to": _header(headers, "To"),
                "date": _header(headers, "Date"),
                "snippet": msg.get("snippet", ""),
                "body": GmailProvider._extract_body(payload),
            })
        return {
            "id": thread.get("id", thread_id),
            "snippet": thread.get("snippet", ""),
            "messages": messages,
        }

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
    def create_draft(to: str, subject: str, body: str, thread_id: Optional[str] = None, credentials=None) -> str:
        service = get_gmail_service(credentials)
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        draft_body: Dict[str, Any] = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        draft = service.users().drafts().create(userId="me", body=draft_body).execute()
        return draft["id"]

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
