from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from jose import jwt as jose_jwt
from auth.google_oauth import get_authorization_url, get_flow, get_user_info, credentials_to_dict
from services.firestore import FirestoreService
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/login")
async def login():
    auth_url, state = get_authorization_url()
    return RedirectResponse(url=auth_url)

@router.get("/callback")
async def callback(request: Request, code: str, state: str = None):
    flow = get_flow()
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

    credentials = flow.credentials
    try:
        user_info = get_user_info(credentials)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not decode id_token: {e}")

    user_id = user_info["email"]
    creds_dict = credentials_to_dict(credentials)
    FirestoreService.store_user_credentials(user_id, user_info, creds_dict)

    token = jose_jwt.encode(
        {
            "sub": user_id,
            "email": user_info["email"],
            "name": user_info.get("name", ""),
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    frontend_url = settings.ALLOWED_ORIGINS.split(",")[0].strip()
    return RedirectResponse(url=f"{frontend_url}/es?token={token}")
