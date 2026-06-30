from googleapiclient.discovery import build
import google.auth
from typing import Dict, Any, List

_SHEETS_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

def get_sheets_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default(scopes=_SHEETS_SCOPES)
    return build('sheets', 'v4', credentials=credentials)

def get_drive_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default(scopes=_SHEETS_SCOPES)
    return build('drive', 'v3', credentials=credentials)

class SheetsService:
    @staticmethod
    def get_spreadsheet(spreadsheet_id: str, credentials=None) -> Dict[str, Any]:
        service = get_sheets_service(credentials)
        return service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

    @staticmethod
    def read_range(spreadsheet_id: str, range_name: str, credentials=None) -> List[List[Any]]:
        service = get_sheets_service(credentials)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        return result.get('values', [])

    @staticmethod
    def create_spreadsheet(title: str, credentials=None) -> str:
        service = get_sheets_service(credentials)
        spreadsheet = service.spreadsheets().create(
            body={'properties': {'title': title}},
            fields='spreadsheetId'
        ).execute()
        spreadsheet_id = spreadsheet.get('spreadsheetId')

        # Share with the user if credentials are user-owned
        if credentials and hasattr(credentials, 'client_id'):
            try:
                drive = get_drive_service(credentials)
                drive.permissions().create(
                    fileId=spreadsheet_id,
                    body={'type': 'anyone', 'role': 'writer'},
                    fields='id',
                ).execute()
            except Exception:
                pass

        return spreadsheet_id

    @staticmethod
    def update_values(spreadsheet_id: str, range_name: str, values: List[List[Any]], credentials=None) -> bool:
        service = get_sheets_service(credentials)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body={'values': values}
        ).execute()
        return True
