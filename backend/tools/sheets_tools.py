import json
from google.adk.tools import ToolContext
from services.sheets import SheetsService

def create_spreadsheet(title: str, tool_context: ToolContext = None) -> str:
    """
    Creates a new Google Spreadsheet and returns the spreadsheet ID.
    Use this when you need to create a new tabular dataset or report.
    """
    try:
        spreadsheet_id = SheetsService.create_spreadsheet(title)
        return json.dumps({
            "status": "success",
            "spreadsheet_id": spreadsheet_id,
            "message": f"Successfully created spreadsheet with title '{title}'."
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def read_spreadsheet_range(spreadsheet_id: str, range_name: str, tool_context: ToolContext = None) -> str:
    """
    Reads values from a specific range in a Google Spreadsheet.
    The range should be in A1 notation, e.g., 'Sheet1!A1:D10' or just 'Sheet1'.
    """
    try:
        values = SheetsService.read_range(spreadsheet_id, range_name)
        if not values:
            return json.dumps({"status": "success", "values": [], "message": "No data found."})
        return json.dumps({
            "status": "success",
            "values": values,
            "message": f"Successfully read {len(values)} rows from range '{range_name}'."
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def update_spreadsheet_values(spreadsheet_id: str, range_name: str, values_json: str, tool_context: ToolContext = None) -> str:
    """
    Updates values in a specific range in a Google Spreadsheet.
    The range should be in A1 notation (e.g. 'Sheet1!A1').
    The values_json should be a JSON string representing a list of lists, where each inner list is a row.
    Example values_json: '[["Header1", "Header2"], ["Value1", "Value2"]]'
    """
    try:
        values = json.loads(values_json)
        SheetsService.update_values(spreadsheet_id, range_name, values)
        return json.dumps({
            "status": "success",
            "message": f"Successfully updated values in range '{range_name}'."
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
