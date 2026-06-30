import google_auth_oauthlib.flow
from typing import Dict
from config import settings

# Keyed by OAuth state; holds the Flow that carries the PKCE code_verifier.
# Cleared on consumption so each state is single-use.
_flow_cache: Dict[str, google_auth_oauthlib.flow.Flow] = {}

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/gmail.modify",
]

def get_flow():
    return google_auth_oauthlib.flow.Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES
    )

def get_authorization_url():
    flow = get_flow()
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    _flow_cache[state] = flow  # preserve code_verifier for the callback
    return auth_url, state


def consume_flow(state: str) -> google_auth_oauthlib.flow.Flow:
    """Return the flow that has the PKCE verifier for this state, or a fresh one."""
    return _flow_cache.pop(state, None) or get_flow()


def get_user_info(credentials) -> dict:
    import google.auth.transport.requests
    import google.oauth2.id_token
    request = google.auth.transport.requests.Request()
    id_info = google.oauth2.id_token.verify_oauth2_token(
        credentials.id_token, request, settings.GOOGLE_CLIENT_ID
    )
    return id_info  # keys: sub, email, name, picture


def credentials_to_dict(credentials) -> dict:
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
    }


def credentials_from_dict(d: dict):
    from google.oauth2.credentials import Credentials
    return Credentials(
        token=d.get("token"),
        refresh_token=d.get("refresh_token"),
        token_uri=d.get("token_uri"),
        client_id=d.get("client_id"),
        client_secret=d.get("client_secret"),
        scopes=d.get("scopes"),
    )
