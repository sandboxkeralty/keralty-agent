import json
from typing import Optional
from google.adk.tools import ToolContext
from services.sheets import SheetsService
from tools._auth import _credentials
from tools._audit import _audit


async def create_spreadsheet(title: str, tool_context: ToolContext, data_json: Optional[str] = None) -> dict:
    """Creates a new Google Spreadsheet, optionally writing initial data into it.

    Args:
        title: The title of the new spreadsheet.
        data_json: Optional JSON string representing a list of lists (rows) to write
            starting at cell A1 of the first tab, e.g. '[["Header1","Header2"],["v1","v2"]]'.
    """
    try:
        creds = _credentials(tool_context)
        created = SheetsService.create_spreadsheet(title, credentials=creds)
        spreadsheet_id = created["spreadsheet_id"]
        first_sheet_title = created["first_sheet_title"]
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

        if data_json:
            try:
                values = json.loads(data_json)
                SheetsService.update_values(
                    spreadsheet_id, f"{first_sheet_title}!A1", values, credentials=creds
                )
            except Exception as e:
                print(f"[create_spreadsheet] data write failed: {e}", flush=True)

        user_id = getattr(getattr(tool_context, 'session', None), 'user_id', None)
        share_target = user_id if (user_id and '@' in str(user_id)) else 'sandboxkeralty@gmail.com'
        try:
            SheetsService.share_spreadsheet(spreadsheet_id, share_target, credentials=creds)
        except Exception:
            pass

        _audit(tool_context, "create_spreadsheet", "spreadsheet", spreadsheet_id)
        return {"status": "success", "spreadsheet_id": spreadsheet_id, "url": url,
                "first_sheet_title": first_sheet_title,
                "message": f"Successfully created spreadsheet '{title}'."}
    except Exception as e:
        print(f"[create_spreadsheet] ERROR: {type(e).__name__}: {e}", flush=True)
        return {"status": "error", "message": str(e)}


async def sheets_list_tabs(spreadsheet_id: str, tool_context: ToolContext) -> dict:
    """Lists the tabs (sheets) inside a Google Spreadsheet, with their titles and IDs.

    Args:
        spreadsheet_id: The ID of the spreadsheet.
    """
    try:
        meta = SheetsService.get_spreadsheet(spreadsheet_id, credentials=_credentials(tool_context))
        tabs = [
            {"sheet_id": s["properties"]["sheetId"], "title": s["properties"]["title"],
             "index": s["properties"]["index"]}
            for s in meta.get("sheets", [])
        ]
        return {"status": "success", "tabs": tabs,
                "message": f"Spreadsheet has {len(tabs)} tab(s)."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def read_spreadsheet_range(spreadsheet_id: str, range_name: str, tool_context: ToolContext) -> dict:
    """Reads values from a specific range in a Google Spreadsheet.

    Args:
        spreadsheet_id: The ID of the spreadsheet.
        range_name: A1 notation range including the tab name, e.g. 'Hoja 1!A1:D10'.
            Call sheets_list_tabs first if you don't already know the real tab name.
    """
    try:
        values = SheetsService.read_range(spreadsheet_id, range_name, credentials=_credentials(tool_context))
        if not values:
            return {"status": "success", "values": [], "message": "No data found."}
        return {"status": "success", "values": values,
                "message": f"Successfully read {len(values)} rows from range '{range_name}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def update_spreadsheet_values(spreadsheet_id: str, range_name: str, values_json: str,
                                     tool_context: ToolContext) -> dict:
    """Overwrites values in a specific range in an existing Google Spreadsheet.

    Args:
        spreadsheet_id: The ID of the spreadsheet.
        range_name: A1 notation range including the tab name, e.g. 'Hoja 1!A1'.
        values_json: JSON string representing a list of lists (rows).
    """
    try:
        creds = _credentials(tool_context)
        values = json.loads(values_json)
        SheetsService.update_values(spreadsheet_id, range_name, values, credentials=creds)
        _audit(tool_context, "update_spreadsheet_values", "spreadsheet", spreadsheet_id)
        return {"status": "success", "message": f"Successfully updated values in range '{range_name}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def append_spreadsheet_values(spreadsheet_id: str, range_name: str, values_json: str,
                                     tool_context: ToolContext) -> dict:
    """Appends rows of data to an existing Google Spreadsheet tab, after the last row with data.
    Use this to add new information without overwriting existing content or needing to know the last row.

    Args:
        spreadsheet_id: The ID of the spreadsheet.
        range_name: The tab name to append to, e.g. 'Hoja 1' (do not include a row/column range).
        values_json: JSON string representing a list of lists (rows) to append.
    """
    try:
        creds = _credentials(tool_context)
        values = json.loads(values_json)
        result = SheetsService.append_values(spreadsheet_id, range_name, values, credentials=creds)
        _audit(tool_context, "append_spreadsheet_values", "spreadsheet", spreadsheet_id)
        return {"status": "success", "updated_range": result.get("updatedRange"),
                "message": f"Successfully appended {len(values)} row(s) to '{range_name}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
