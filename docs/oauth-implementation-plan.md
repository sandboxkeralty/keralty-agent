# Plan: OAuth Token Storage & Injection (Step 2)

## Context

The `/auth/login` → Google consent redirect works, but the callback discards the returned credentials. All Workspace API calls (Drive, Docs, Sheets, Slides, Gmail) use `google.auth.default()` (service account), so they fail or act as the wrong identity. The goal is to close the full loop: store the user's OAuth token after consent, issue a real JWT session, and thread those credentials through the ADK agent pipeline so every tool call executes as the logged-in user.

---

## Architecture

```
Browser                Backend                      Firestore / ADK
  │                       │                              │
  ├─ GET /auth/login ────►│─ redirect to Google          │
  │◄── Google consent ───►│                              │
  │                       │─ exchange code for tokens    │
  │                       │─ decode id_token → email ──►│ upsert users/{uid}
  │                       │  mint JWT (python-jose)      │   {email, name, picture,
  │◄── redirect ?token=xx─┤                              │    google_credentials:{...}}
  │ store in localStorage  │                              │
  │                       │                              │
  ├─ POST /api/chat ──────►│ verify JWT → user_id         │
  │  Auth: Bearer {jwt}    │─ load creds ───────────────►│ get users/{uid}.google_credentials
  │                       │─ inject into ADK session.state│
  │                       │─ runner.run_async(...)        │
  │                       │   tool reads state["google_credentials"]
  │                       │   → build API client with user token
```

---

## Implementation

### 1 — `backend/auth/google_oauth.py` (extend, don't rewrite)

Add three helpers below the existing `get_authorization_url()`:

```python
def get_user_info(credentials):
    """Decode the id_token to get sub, email, name, picture."""
    import google.auth.transport.requests, google.oauth2.id_token
    request = google.auth.transport.requests.Request()
    id_info = google.oauth2.id_token.verify_oauth2_token(
        credentials.id_token, request, settings.GOOGLE_CLIENT_ID)
    return id_info  # keys: sub, email, name, picture

def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
    }

def credentials_from_dict(d):
    from google.oauth2.credentials import Credentials
    return Credentials(
        token=d["token"],
        refresh_token=d["refresh_token"],
        token_uri=d["token_uri"],
        client_id=d["client_id"],
        client_secret=d["client_secret"],
        scopes=d["scopes"],
    )
```

---

### 2 — `backend/services/firestore.py` (add 2 methods)

Add to `FirestoreService`:

```python
@staticmethod
def store_user_credentials(user_id: str, user_info: dict, creds_dict: dict):
    db.collection("users").document(user_id).set({
        "user_id": user_id,
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "picture": user_info.get("picture"),
        "google_credentials": creds_dict,
        "updated_at": datetime.now(timezone.utc),
    }, merge=True)

@staticmethod
def get_user_credentials(user_id: str) -> Optional[dict]:
    doc = db.collection("users").document(user_id).get()
    if doc.exists:
        return doc.to_dict().get("google_credentials")
    return None
```

---

### 3 — `backend/routers/auth.py` (complete the callback)

```python
from jose import jwt as jose_jwt
from auth.google_oauth import get_flow, get_user_info, credentials_to_dict
from services.firestore import FirestoreService
from config import settings
from datetime import datetime, timezone, timedelta

@router.get("/callback")
async def callback(request: Request, code: str, state: str = None):
    flow = get_flow()
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    flow.fetch_token(code=code)
    credentials = flow.credentials

    user_info = get_user_info(credentials)
    user_id = user_info["email"]          # use email as stable user_id

    creds_dict = credentials_to_dict(credentials)
    FirestoreService.store_user_credentials(user_id, user_info, creds_dict)

    token = jose_jwt.encode(
        {"sub": user_id, "email": user_info["email"],
         "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        settings.SECRET_KEY, algorithm="HS256"
    )

    frontend_url = settings.ALLOWED_ORIGINS.split(",")[0].strip()
    return RedirectResponse(url=f"{frontend_url}/?token={token}")
```

---

### 4 — `backend/auth/auth_middleware.py` (replace stub with real JWT verification)

```python
from jose import jwt as jose_jwt, JWTError
from config import settings

async def auth_middleware(request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/auth"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing token"})
        token = auth_header.split(" ")[1]
        try:
            payload = jose_jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            request.state.user = {"uid": payload["sub"], "email": payload["email"]}
        except JWTError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

    return await call_next(request)
```

---

### 5 — `backend/routers/chat.py` (inject Request + credentials into session state)

```python
from fastapi import APIRouter, HTTPException, Depends, Request as FastAPIRequest
from services.firestore import FirestoreService

@router.post("")
async def chat_endpoint(request: ChatRequest, http_request: FastAPIRequest):
    user_id = getattr(http_request.state, "user", {}).get("uid", request.user_id)

    async def sse_generator():
        creds_dict = FirestoreService.get_user_credentials(user_id)

        try:
            session = await runner.session_service.get_session(
                app_name="agents", session_id=request.session_id, user_id=user_id)
            if session is None:
                await runner.session_service.create_session(
                    app_name="agents", user_id=user_id,
                    session_id=request.session_id,
                    state={"google_credentials": creds_dict} if creds_dict else {}
                )
            elif creds_dict:
                session.state["google_credentials"] = creds_dict
        except Exception as e:
            print(f"Session error: {e}")

        async for event in runner.run_async(
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=request.message)]),
            session_id=request.session_id,
            user_id=user_id
        ):
            # ... rest of streaming logic unchanged
```

---

### 6 — Service factories: accept optional credentials (same pattern × 4)

**Files**: `backend/services/drive.py`, `docs.py`, `sheets.py`, `slides.py`

```python
# BEFORE
def get_drive_service():
    credentials, _ = google.auth.default()
    return build('drive', 'v3', credentials=credentials)

# AFTER
def get_drive_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default()
    return build('drive', 'v3', credentials=credentials)
```

All class methods that call the factory forward the `credentials` param:
```python
@staticmethod
def list_documents(query=None, limit=10, credentials=None):
    service = get_drive_service(credentials)
    ...
```

---

### 7 — Tools: extract credentials from tool_context.state (same pattern × 4)

**Files**: `backend/tools/drive_tools.py`, `docs_tools.py`, `sheets_tools.py`, `slides_tools.py`

Create `backend/tools/_auth.py` (shared helper):
```python
from auth.google_oauth import credentials_from_dict

def _credentials(tool_context):
    creds_dict = getattr(tool_context, "state", {}).get("google_credentials")
    return credentials_from_dict(creds_dict) if creds_dict else None
```

Each tool passes credentials to the service:
```python
from tools._auth import _credentials

async def drive_read(file_id: str, tool_context: ToolContext) -> dict:
    text = DriveService.read_document_text(file_id, credentials=_credentials(tool_context))
    return {"status": "success", "text": text}
```

---

### 8 — `frontend/components/layout/Navbar.tsx`

```tsx
"use client";
import { useEffect, useState } from "react";

export function Navbar() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      localStorage.setItem("keralty_token", token);
      window.history.replaceState({}, "", window.location.pathname);
    }
    setLoggedIn(!!localStorage.getItem("keralty_token"));
  }, []);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    // existing JSX structure...
    // add inside the header:
    // {loggedIn
    //   ? <button onClick={() => { localStorage.removeItem("keralty_token"); setLoggedIn(false); }}>Cerrar sesión</button>
    //   : <a href={`${apiUrl}/auth/login`}>Iniciar sesión</a>
    // }
  );
}
```

---

### 9 — `frontend/components/chat/ChatWindow.tsx`

Replace hardcoded auth header and add real session/user IDs:

```tsx
// Replace the fetch call headers + body:
const token = localStorage.getItem("keralty_token") ?? "test-token";
const sessionId = sessionStorage.getItem("keralty_session") ?? (() => {
  const id = crypto.randomUUID();
  sessionStorage.setItem("keralty_session", id);
  return id;
})();

fetch(`${apiUrl}/api/chat`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`,
  },
  body: JSON.stringify({
    message: userMessage.content,
    session_id: sessionId,
  }),
});
```

---

## Files Modified Summary

| Layer | File | Change |
|---|---|---|
| Auth helpers | `backend/auth/google_oauth.py` | Add `get_user_info`, `credentials_to_dict`, `credentials_from_dict` |
| Auth middleware | `backend/auth/auth_middleware.py` | Verify real JWT; set `request.state.user` from claims |
| OAuth callback | `backend/routers/auth.py` | Store tokens, mint JWT, redirect with token |
| Chat router | `backend/routers/chat.py` | Inject FastAPI Request; load + inject creds into session state |
| Firestore | `backend/services/firestore.py` | Add `store_user_credentials`, `get_user_credentials` |
| Services (×4) | `drive.py`, `docs.py`, `sheets.py`, `slides.py` | Optional `credentials` param on factory + class methods |
| Tools shared | `backend/tools/_auth.py` | New file — `_credentials(tool_context)` helper |
| Tools (×4) | `drive_tools.py`, `docs_tools.py`, `sheets_tools.py`, `slides_tools.py` | Import `_credentials`, pass to services |
| Frontend Navbar | `frontend/components/layout/Navbar.tsx` | Token capture from URL, login/logout button |
| Frontend Chat | `frontend/components/chat/ChatWindow.tsx` | Real JWT in Authorization header, real session_id |

---

## Verification

1. Visit `https://keralty-agent-frontend-569920970367.us-central1.run.app` → Navbar shows "Iniciar sesión"
2. Click → Google consent page → approve all scopes → redirected back to frontend with `?token=xxx` stripped from URL
3. Navbar now shows "Cerrar sesión"
4. Ask the agent "lista los archivos de mi Drive" → returns real files from the user's Drive
5. Ask "crea una hoja de cálculo de prueba" → creates a real Spreadsheet in the user's Google Drive
6. Check Firestore console → `users/sandboxkeralty@gmail.com` document has `google_credentials` field

---

## Current Status (before this plan is executed)

- Auth middleware: accepts any Bearer token, hardcodes `sandbox-user` ✅ (working for testing)
- Workspace API calls: use service account ADC (permission errors on user-owned files) ⚠️
- OAuth callback: redirect to Google works, token discarded ⚠️
