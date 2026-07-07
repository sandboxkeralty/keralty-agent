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
    'application/vnd.google-apps.spreadsheet',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'text/plain',
    'text/csv',
    'text/markdown',
]
_MIME_TYPE_ALIASES = {
    'document': ['application/vnd.google-apps.document'],
    'presentation': ['application/vnd.google-apps.presentation'],
    'spreadsheet': [
        'application/vnd.google-apps.spreadsheet',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
    ],
}

# Non-native files whose raw bytes we can run through the same text extractor
# used for local chat uploads (services/rag/ingestion.py's extract_text) —
# mirrors the pattern services/sheets.py already uses for raw .xlsx files:
# download via Drive's get_media rather than a format-specific export API.
_EXTRACTABLE_MIME_TO_FILETYPE = {
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/msword': 'doc',
    'text/plain': 'txt',
    'text/csv': 'csv',
    'text/markdown': 'md',
}

class DriveService:
    @staticmethod
    def list_documents(query: str = None, limit: int = 10, credentials=None,
                        mime_types: List[str] = None) -> List[Dict[str, Any]]:
        service = get_drive_service(credentials)
        types = mime_types if mime_types else _DEFAULT_MIME_TYPES
        resolved = []
        for t in types:
            resolved.extend(_MIME_TYPE_ALIASES.get(t, [t]))
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
            if mime_type in (
                'application/vnd.google-apps.spreadsheet',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-excel',
            ):
                from services.sheets import SheetsService
                meta = SheetsService.get_spreadsheet(file_id, credentials=credentials)
                tabs = [s['properties']['title'] for s in meta.get('sheets', [])]
                return (f"Spreadsheet with tabs: {', '.join(tabs)}. "
                        "Use sheets_list_tabs and read_spreadsheet_range to read specific tab contents.")
            filetype = _EXTRACTABLE_MIME_TO_FILETYPE.get(mime_type)
            if filetype:
                data = service.files().get_media(fileId=file_id).execute()
                from services.rag.ingestion import extract_text
                return extract_text(data, filetype)
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
