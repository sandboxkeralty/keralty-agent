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
