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
    def create_spreadsheet(title: str, credentials=None) -> Dict[str, Any]:
        service = get_sheets_service(credentials)
        spreadsheet = service.spreadsheets().create(
            body={'properties': {'title': title}},
            fields='spreadsheetId,sheets.properties'
        ).execute()
        spreadsheet_id = spreadsheet.get('spreadsheetId')
        sheets = spreadsheet.get('sheets', [])
        first_sheet_title = sheets[0]['properties']['title'] if sheets else 'Sheet1'
        return {'spreadsheet_id': spreadsheet_id, 'first_sheet_title': first_sheet_title}

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

    @staticmethod
    def append_values(spreadsheet_id: str, range_name: str, values: List[List[Any]], credentials=None) -> Dict[str, Any]:
        service = get_sheets_service(credentials)
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': values}
        ).execute()
        return result.get('updates', {})

    @staticmethod
    def share_spreadsheet(spreadsheet_id: str, email: str, credentials=None) -> None:
        service = get_drive_service(credentials)
        service.permissions().create(
            fileId=spreadsheet_id,
            body={'type': 'user', 'role': 'writer', 'emailAddress': email},
            fields='id',
            sendNotificationEmail=False,
        ).execute()
