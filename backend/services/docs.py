from googleapiclient.discovery import build
import google.auth
from typing import Dict, Any

def get_docs_service():
    credentials, _ = google.auth.default()
    return build('docs', 'v1', credentials=credentials)

def get_drive_service():
    credentials, _ = google.auth.default()
    return build('drive', 'v3', credentials=credentials)

class DocsService:
    @staticmethod
    def get_document(document_id: str) -> Dict[str, Any]:
        service = get_docs_service()
        doc = service.documents().get(documentId=document_id).execute()
        return doc
        
    @staticmethod
    def create_document(title: str) -> str:
        service = get_docs_service()
        doc = service.documents().create(body={"title": title}).execute()
        return doc.get('documentId')
        
    @staticmethod
    def append_text(document_id: str, text: str) -> bool:
        service = get_docs_service()
        # Find the end of the document
        doc = service.documents().get(documentId=document_id).execute()
        content = doc.get('body', {}).get('content', [])
        end_index = content[-1].get('endIndex') - 1 if content else 1
        
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': end_index,
                    },
                    'text': text + "\n"
                }
            }
        ]
        service.documents().batchUpdate(documentId=document_id, body={'requests': requests}).execute()
        return True
