from googleapiclient.discovery import build
import google.auth
from typing import List, Dict, Any

_DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default(scopes=_DRIVE_SCOPES)
    return build('drive', 'v3', credentials=credentials)

_DEFAULT_MIME_TYPES = [
    'application/vnd.google-apps.document',
    'application/vnd.google-apps.presentation',
]
_MIME_TYPE_ALIASES = {
    'document': 'application/vnd.google-apps.document',
    'presentation': 'application/vnd.google-apps.presentation',
    'spreadsheet': 'application/vnd.google-apps.spreadsheet',
}

class DriveService:
    @staticmethod
    def list_documents(query: str = None, limit: int = 10, credentials=None,
                        mime_types: List[str] = None) -> List[Dict[str, Any]]:
        service = get_drive_service(credentials)
        types = mime_types if mime_types else _DEFAULT_MIME_TYPES
        resolved = [_MIME_TYPE_ALIASES.get(t, t) for t in types]
        mime_clause = " or ".join(f"mimeType='{t}'" for t in resolved)
        q = f"({mime_clause})"
        if query:
            q += f" and name contains '{query}'"

        results = service.files().list(
            q=q,
            pageSize=limit,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, iconLink)",
            orderBy="modifiedTime desc"
        ).execute()

        return results.get('files', [])

    @staticmethod
    def read_document_text(file_id: str, credentials=None) -> str:
        service = get_drive_service(credentials)
        file = service.files().get(fileId=file_id, fields="mimeType").execute()
        mime_type = file.get("mimeType")

        try:
            if mime_type in (
                'application/vnd.google-apps.document',
                'application/vnd.google-apps.presentation',
            ):
                response = service.files().export_media(fileId=file_id, mimeType='text/plain').execute()
                return response.decode('utf-8')
            if mime_type == 'application/vnd.google-apps.spreadsheet':
                from services.sheets import SheetsService
                meta = SheetsService.get_spreadsheet(file_id, credentials=credentials)
                tabs = [s['properties']['title'] for s in meta.get('sheets', [])]
                return (f"Spreadsheet with tabs: {', '.join(tabs)}. "
                        "Use sheets_list_tabs and read_spreadsheet_range to read specific tab contents.")
            return "Unsupported file type."
        except Exception as e:
            return f"Error reading document: {str(e)}"

    @staticmethod
    def export_pdf(file_id: str, credentials=None) -> bytes:
        service = get_drive_service(credentials)
        try:
            return service.files().export_media(fileId=file_id, mimeType='application/pdf').execute()
        except Exception as e:
            raise ValueError(f"Error exporting to PDF: {str(e)}")
