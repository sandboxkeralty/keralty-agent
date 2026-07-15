"""Executive news endpoints (see services/news_service.py).

Mounted at /api/news so the standard auth middleware covers it. The cache is
global (news isn't user-specific), so any user's refresh benefits everyone.
"""

from fastapi import APIRouter, HTTPException, Request

from services import news_service

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
async def get_news(request: Request):
    try:
        return news_service.get_news()
    except Exception as e:
        print(f"[news] get failed: {e}", flush=True)
        raise HTTPException(status_code=502, detail="News fetch failed; try again.")


@router.post("/refresh")
async def refresh_news(request: Request):
    try:
        return news_service.get_news(force_refresh=True)
    except Exception as e:
        print(f"[news] refresh failed: {e}", flush=True)
        raise HTTPException(status_code=502, detail="News refresh failed; try again.")
