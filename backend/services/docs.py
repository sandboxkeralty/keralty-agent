from googleapiclient.discovery import build
import google.auth
from typing import Dict, Any, Optional

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

        requests = [
            {
                'insertText': {
                    'location': {'index': end_index},
                    'text': text + "\n"
                }
            }
        ]
        service.documents().batchUpdate(documentId=document_id, body={'requests': requests}).execute()
        return True
