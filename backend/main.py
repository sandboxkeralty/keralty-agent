from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth
from config import settings

app = FastAPI(title="Keralty Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
