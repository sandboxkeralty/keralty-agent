from googleapiclient.discovery import build
import google.auth
from typing import List, Dict, Any

def get_drive_service():
    credentials, _ = google.auth.default()
    return build('drive', 'v3', credentials=credentials)

class DriveService:
    @staticmethod
    def list_documents(query: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        service = get_drive_service()
        q = "mimeType='application/vnd.google-apps.document' or mimeType='application/vnd.google-apps.presentation'"
        if query:
            # simple filter, a more robust one would escape quotes
            q += f" and name contains '{query}'"
            
        results = service.files().list(
            q=q,
            pageSize=limit,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, iconLink)",
            orderBy="modifiedTime desc"
        ).execute()
        
        return results.get('files', [])

    @staticmethod
    def read_document_text(file_id: str) -> str:
        service = get_drive_service()
        file = service.files().get(fileId=file_id, fields="mimeType").execute()
        mime_type = file.get("mimeType")

        try:
            if mime_type == 'application/vnd.google-apps.document':
                response = service.files().export_media(fileId=file_id, mimeType='text/plain').execute()
                return response.decode('utf-8')
            elif mime_type == 'application/vnd.google-apps.presentation':
                response = service.files().export_media(fileId=file_id, mimeType='text/plain').execute()
                return response.decode('utf-8')
            return "Unsupported file type."
        except Exception as e:
            return f"Error reading document: {str(e)}"

    @staticmethod
    def export_pdf(file_id: str) -> bytes:
        service = get_drive_service()
        try:
            response = service.files().export_media(fileId=file_id, mimeType='application/pdf').execute()
            return response
        except Exception as e:
            raise ValueError(f"Error exporting to PDF: {str(e)}")
