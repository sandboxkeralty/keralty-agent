from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from auth.auth_middleware import auth_middleware
from routers import auth, documents, voice, history, admin, knowledge, chat, tasks, email, tts, style, signatures, news, folders
from config import settings
from observability.tracing import setup_tracing

app = FastAPI(title="Keralty Agent API")

setup_tracing(app)

app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

# Registered last so CORSMiddleware is the OUTERMOST middleware (Starlette wraps
# in reverse registration order). It must wrap the auth middleware: a 401 short-
# circuited by auth would otherwise leave the server without CORS headers, and
# browsers surface that as an opaque "Failed to fetch" instead of a 401 the
# frontend can catch to redirect to login.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(voice.router)
# folders BEFORE history: the fixed /history/folders path must win over /history/{session_id}
app.include_router(folders.router)
app.include_router(history.router)
app.include_router(admin.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(email.router)
app.include_router(tts.router)
app.include_router(style.router)
app.include_router(signatures.router)
app.include_router(news.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
