import re

from googleapiclient.discovery import build
import google.auth
from typing import Dict, Any, List, Optional, Tuple

_DOCS_SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
]

def get_docs_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default(scopes=_DOCS_SCOPES)
    return build('docs', 'v1', credentials=credentials)

def get_drive_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default(scopes=_DOCS_SCOPES)
    return build('drive', 'v3', credentials=credentials)

# ── Markdown → native Docs formatting ──────────────────────────────────────
# The agents deliberately draft in Markdown (WritingAgent's instruction says
# so); inserting that raw left literal `#`/`**` characters in generated Docs.
# Strategy: strip the syntax while recording ranges, insert the clean text in
# ONE insertText, then apply styling requests against the final coordinates
# (safe because none of the style requests shift indexes — no leading tabs).

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_MD_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_MD_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_MD_HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_MD_INLINE = re.compile(
    r"\*\*(?P<bold>.+?)\*\*"
    r"|\*(?P<italic>[^\s*][^*\n]*?)\*"
    r"|`(?P<code>[^`\n]+?)`"
    r"|\[(?P<linktext>[^\]]+)\]\((?P<url>[^)\s]+)\)"
)


def _strip_inline_md(line: str) -> Tuple[str, List[Tuple[int, int, str, Optional[str]]]]:
    """Removes inline markdown from a line; returns (plain, [(start, end, kind, extra)])
    with offsets into the plain text."""
    out: List[str] = []
    styles: List[Tuple[int, int, str, Optional[str]]] = []
    pos = 0
    plain_len = 0
    for m in _MD_INLINE.finditer(line):
        out.append(line[pos:m.start()])
        plain_len += m.start() - pos
        if m.group("bold") is not None:
            seg, kind, extra = m.group("bold"), "bold", None
        elif m.group("italic") is not None:
            seg, kind, extra = m.group("italic"), "italic", None
        elif m.group("code") is not None:
            seg, kind, extra = m.group("code"), "code", None
        else:
            seg, kind, extra = m.group("linktext"), "link", m.group("url")
        # Nested bold inside links / bold+italic combos are left as-is (rare).
        styles.append((plain_len, plain_len + len(seg), kind, extra))
        out.append(seg)
        plain_len += len(seg)
        pos = m.end()
    out.append(line[pos:])
    return "".join(out), styles


def markdown_to_docs_requests(md: str, start: int) -> List[Dict[str, Any]]:
    """Builds a batchUpdate request list that inserts `md` at `start` rendered
    with native Docs formatting (headings, bullets, numbered lists, bold,
    italic, links, inline code) instead of literal markdown syntax."""
    lines = md.replace("\r\n", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    paras = []  # (start_off, end_off, kind, level, inline_styles)
    parts: List[str] = []
    offset = 0
    for raw in lines:
        kind, level, line = "normal", 0, raw
        m = _MD_HEADING.match(raw)
        if m:
            kind, level, line = "heading", len(m.group(1)), m.group(2)
        elif _MD_HR.match(raw):
            line = ""
        else:
            mb = _MD_BULLET.match(raw)
            mn = _MD_NUMBERED.match(raw)
            if mb:
                kind, line = "bullet", mb.group(1)
            elif mn:
                kind, line = "numbered", mn.group(1)
        plain, styles = _strip_inline_md(line)
        text = plain + "\n"
        paras.append((offset, offset + len(text), kind, level, styles))
        parts.append(text)
        offset += len(text)

    full_text = "".join(parts)
    if not full_text.strip():
        return []
    requests: List[Dict[str, Any]] = [
        {"insertText": {"location": {"index": start}, "text": full_text}}
    ]
    for p_start, p_end, kind, level, styles in paras:
        a, b = start + p_start, start + p_end
        if kind == "heading":
            requests.append({"updateParagraphStyle": {
                "range": {"startIndex": a, "endIndex": b},
                "paragraphStyle": {"namedStyleType": f"HEADING_{min(level, 6)}"},
                "fields": "namedStyleType",
            }})
        for s0, s1, skind, extra in styles:
            if s1 <= s0:
                continue
            rng = {"startIndex": a + s0, "endIndex": a + s1}
            if skind == "bold":
                requests.append({"updateTextStyle": {
                    "range": rng, "textStyle": {"bold": True}, "fields": "bold"}})
            elif skind == "italic":
                requests.append({"updateTextStyle": {
                    "range": rng, "textStyle": {"italic": True}, "fields": "italic"}})
            elif skind == "code":
                requests.append({"updateTextStyle": {
                    "range": rng,
                    "textStyle": {"weightedFontFamily": {"fontFamily": "Courier New"}},
                    "fields": "weightedFontFamily"}})
            elif skind == "link":
                requests.append({"updateTextStyle": {
                    "range": rng, "textStyle": {"link": {"url": extra}}, "fields": "link"}})

    # Contiguous list lines must share ONE createParagraphBullets range —
    # per-paragraph requests would restart numbered lists at 1 on every line.
    run_start = None
    run_kind = None
    runs = []
    for p_start, p_end, kind, _level, _styles in paras + [(offset, offset, "end", 0, [])]:
        if kind in ("bullet", "numbered"):
            if run_kind == kind:
                run_end = p_end
                continue
            if run_start is not None:
                runs.append((run_start, run_end, run_kind))
            run_start, run_end, run_kind = p_start, p_end, kind
        else:
            if run_start is not None:
                runs.append((run_start, run_end, run_kind))
                run_start = run_kind = None
    for r_start, r_end, kind in runs:
        requests.append({"createParagraphBullets": {
            "range": {"startIndex": start + r_start, "endIndex": start + r_end},
            "bulletPreset": ("BULLET_DISC_CIRCLE_SQUARE" if kind == "bullet"
                             else "NUMBERED_DECIMAL_ALPHA_ROMAN"),
        }})
    return requests


class DocsService:
    @staticmethod
    def get_document(document_id: str, credentials=None) -> Dict[str, Any]:
        service = get_docs_service(credentials)
        doc = service.documents().get(documentId=document_id).execute()
        return doc

    @staticmethod
    def create_document(title: str, credentials=None) -> str:
        service = get_docs_service(credentials)
        doc = service.documents().create(body={"title": title}).execute()
        return doc.get('documentId')

    @staticmethod
    def share_document(document_id: str, email: str, credentials=None) -> None:
        service = get_drive_service(credentials)
        service.permissions().create(
            fileId=document_id,
            body={'type': 'user', 'role': 'writer', 'emailAddress': email},
            fields='id',
            sendNotificationEmail=False,
        ).execute()

    @staticmethod
    def append_signature(document_id: str, content: str, logo_url: Optional[str] = None,
                         credentials=None) -> bool:
        """Appends a signature block (text + optional logo image) at the end of a Doc.

        The logo must be a publicly accessible PNG/JPEG URL — the Docs API's
        insertInlineImage fetches it server-side (signature logos live on the
        public GCS bucket under signatures/, uploaded via /api/signatures/logo).
        A failed image insert must not lose the text: it's a separate request in
        the same batch order (text first), and on batch failure we retry text-only.
        """
        service = get_docs_service(credentials)

        def _end_index() -> int:
            doc = service.documents().get(documentId=document_id).execute()
            body = doc.get('body', {}).get('content', [])
            return body[-1].get('endIndex') - 1 if body else 1

        text = "\n" + content.strip() + "\n"
        requests = [{
            'insertText': {'location': {'index': _end_index()}, 'text': text}
        }]
        if logo_url:
            requests.append({
                'insertInlineImage': {
                    'location': {'index': _end_index() + len(text)},
                    'uri': logo_url,
                    'objectSize': {'height': {'magnitude': 50, 'unit': 'PT'}},
                }
            })
        try:
            service.documents().batchUpdate(
                documentId=document_id, body={'requests': requests}).execute()
        except Exception as e:
            if logo_url:
                print(f"[docs] signature logo insert failed ({e}) — retrying text-only", flush=True)
                service.documents().batchUpdate(
                    documentId=document_id, body={'requests': requests[:1]}).execute()
            else:
                raise
        return True

    @staticmethod
    def insert_logo_header(document_id: str, credentials=None) -> bool:
        """Inserts the authorized Keralty logo (Azul Horizontal — docs are
        white-background) at the top of a Doc. Same public-URL
        insertInlineImage mechanics as append_signature; a failure never
        breaks the document — it just stays logo-less."""
        from services import brand
        service = get_docs_service(credentials)
        try:
            service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': [{'insertInlineImage': {
                    'location': {'index': 1},
                    'uri': brand.logo_for_background('white'),
                    'objectSize': {'height': {'magnitude': 40, 'unit': 'PT'}},
                }}]}).execute()
            return True
        except Exception as e:
            print(f"[docs] logo header insert failed ({e}) — document stays logo-less", flush=True)
            return False

    @staticmethod
    def append_text(document_id: str, text: str, credentials=None) -> bool:
        service = get_docs_service(credentials)
        doc = service.documents().get(documentId=document_id).execute()
        content = doc.get('body', {}).get('content', [])
        end_index = content[-1].get('endIndex') - 1 if content else 1

        requests = markdown_to_docs_requests(text, end_index)
        if not requests:
            return True
        try:
            service.documents().batchUpdate(
                documentId=document_id, body={'requests': requests}).execute()
        except Exception as e:
            # A styling request the API rejects must never lose the content:
            # fall back to inserting the raw text unformatted.
            print(f"[docs] markdown render failed ({e}) — falling back to plain text", flush=True)
            service.documents().batchUpdate(documentId=document_id, body={'requests': [
                {'insertText': {'location': {'index': end_index}, 'text': text + "\n"}}
            ]}).execute()
        return True
