from auth.google_oauth import credentials_from_dict, credentials_to_dict

def _credentials(tool_context):
    """Extract user OAuth credentials from ADK session state, or return None to fall back to ADC.
    Auto-refreshes expired tokens and re-persists to Firestore.
    """
    state = getattr(tool_context, "state", {}) if tool_context else {}
    creds_dict = state.get("google_credentials")
    if not creds_dict:
        return None
    creds = credentials_from_dict(creds_dict)
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request as GRequest
            creds.refresh(GRequest())
            refreshed = credentials_to_dict(creds)
            state["google_credentials"] = refreshed
            user_id = state.get("user_id")
            if user_id:
                from services.firestore import FirestoreService
                FirestoreService.store_user_credentials(user_id, {}, refreshed)
        except Exception as e:
            print(f"[_auth] Token refresh failed: {e}")
    return creds
