"""Chat folder management (see services/folder_service.py).

Prefix /history/folders keeps it under the auth middleware's /history scope.
IMPORTANT: this router must be registered BEFORE history.router in main.py so
the fixed "/history/folders" path wins over history's "/history/{session_id}".
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from agents.runner import runner
from services import folder_service
from services.firestore import FirestoreService

router = APIRouter(prefix="/history/folders", tags=["folders"])


def _user_id(request: Request) -> str:
    user = getattr(request.state, "user", {}) or {}
    uid = user.get("email") or user.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return uid


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=folder_service.MAX_NAME_CHARS)


class FolderRename(BaseModel):
    name: str = Field(min_length=1, max_length=folder_service.MAX_NAME_CHARS)


@router.get("")
async def list_folders(request: Request):
    return {"folders": folder_service.list_user_folders(_user_id(request))}


@router.post("", status_code=201)
async def create_folder(request: Request, body: FolderCreate):
    return folder_service.create_folder(_user_id(request), body.name)


@router.patch("/{folder_id}")
async def rename_folder(folder_id: str, request: Request, body: FolderRename):
    updated = folder_service.rename_folder(folder_id, _user_id(request), body.name)
    if updated is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    return updated


@router.delete("/{folder_id}")
async def delete_folder(folder_id: str, request: Request,
                        delete_chats: bool = Query(False)):
    """Deletes a folder. delete_chats=false moves its chats to "Sin carpeta";
    delete_chats=true purges them (messages + ADK memory) — audit_events are
    never touched either way."""
    user_id = _user_id(request)
    if folder_service.get_folder(folder_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Folder not found")

    session_ids = folder_service.sessions_in_folder(user_id, folder_id)
    purged = 0
    for sid in session_ids:
        if delete_chats:
            FirestoreService.purge_session_data(sid)
            await runner.session_service.delete_session(
                app_name="agents", user_id=user_id, session_id=sid
            )
            purged += 1
        else:
            FirestoreService.set_session_folder(sid, None)

    folder_service.delete_folder(folder_id, user_id)
    return {"deleted": True, "chats_purged": purged,
            "chats_unfiled": 0 if delete_chats else len(session_ids)}
