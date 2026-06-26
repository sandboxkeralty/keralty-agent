from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from auth.google_oauth import get_authorization_url, get_flow
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
        raise HTTPException(status_code=400, detail="Invalid code")
    
    credentials = flow.credentials
    # Note: A real implementation would verify user via id_token,
    # create a session in Firestore, and set a secure HttpOnly cookie.
    
    # Redirect back to frontend
    return RedirectResponse(url="http://localhost:3000/")
