from auth.google_oauth import credentials_from_dict

def _credentials(tool_context):
    """Extract user OAuth credentials from ADK session state, or return None to fall back to ADC."""
    creds_dict = getattr(tool_context, "state", {}).get("google_credentials") if tool_context else None
    return credentials_from_dict(creds_dict) if creds_dict else None
