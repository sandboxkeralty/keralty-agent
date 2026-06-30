from googleapiclient.discovery import build
import google.auth
from typing import Dict, Any, List

def get_sheets_service():
    credentials, _ = google.auth.default()
    return build('sheets', 'v4', credentials=credentials)

class SheetsService:
    @staticmethod
    def get_spreadsheet(spreadsheet_id: str) -> Dict[str, Any]:
        """Gets spreadsheet metadata."""
        service = get_sheets_service()
        return service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

    @staticmethod
    def read_range(spreadsheet_id: str, range_name: str) -> List[List[Any]]:
        """Reads values from a specific range in a spreadsheet."""
        service = get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        return result.get('values', [])

    @staticmethod
    def create_spreadsheet(title: str) -> str:
        """Creates a new spreadsheet."""
        service = get_sheets_service()
        spreadsheet = {
            'properties': {
                'title': title
            }
        }
        spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        return spreadsheet.get('spreadsheetId')

    @staticmethod
    def update_values(spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> bool:
        """Updates values in a specific range."""
        service = get_sheets_service()
        body = {
            'values': values
        }
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', body=body).execute()
        return True
