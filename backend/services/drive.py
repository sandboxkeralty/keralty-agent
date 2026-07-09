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

# Same cap as the local-upload endpoint (routers/documents.py). A Drive file
# larger than this is refused before download so a multi-hundred-MB PDF/workbook
# can't OOM the Cloud Run container (which runs at ~512MB–1GB).
_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


class DriveReadError(Exception):
    """Raised when a Drive document cannot be read as text. Callers must surface
    this as an error status — never let its message leak into prompt context as
    if it were document content."""


def _escape_drive_query(value: str) -> str:
    r"""Escapes a user/LLM string for safe interpolation into a Drive `q` clause.
    Per the Drive API, `\` and `'` inside a string literal must be backslash-escaped.
    Without this, an apostrophe (e.g. "Board's report") 400s the request, and a
    crafted value can break out of the literal to alter query semantics (injection).
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


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
            q += f" and name contains '{_escape_drive_query(query)}'"

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
        try:
            file = service.files().get(fileId=file_id, fields="mimeType, size").execute()
        except Exception as e:
            raise DriveReadError(f"Could not open document: {e}")
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
                # Drive reports `size` only for binary (non-native) files — exactly
                # this branch — so cap before pulling the bytes into memory.
                size = int(file.get("size") or 0)
                if size > _MAX_DOWNLOAD_BYTES:
                    raise DriveReadError(
                        f"File is too large to attach ({size // (1024 * 1024)} MB; limit 50 MB)."
                    )
                data = service.files().get_media(fileId=file_id).execute()
                from services.rag.ingestion import extract_text
                return extract_text(data, filetype)
            raise DriveReadError(f"Unsupported file type: {mime_type}")
        except DriveReadError:
            raise
        except Exception as e:
            raise DriveReadError(f"Error reading document: {e}")

    @staticmethod
    def copy_file(file_id: str, new_title: str, credentials=None) -> str:
        """Copies a Drive file (used to instantiate the Slides template per deck)."""
        service = get_drive_service(credentials)
        result = service.files().copy(
            fileId=file_id,
            body={"name": new_title},
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return result["id"]

    @staticmethod
    def export_pdf(file_id: str, credentials=None) -> bytes:
        service = get_drive_service(credentials)
        try:
            return service.files().export_media(fileId=file_id, mimeType='application/pdf').execute()
        except Exception as e:
            raise ValueError(f"Error exporting to PDF: {str(e)}")
