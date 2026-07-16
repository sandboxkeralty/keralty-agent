"""Chat model catalog for the frontend picker.

/api/ prefix ⇒ covered by the standard auth middleware. Only key-backed models
are listed, so the picker never offers a model that would silently fall back.
"""

from fastapi import APIRouter

from services.model_registry import DEFAULT_MODEL_KEY, available_models

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
@router.get("/")
def list_models():
    return {
        "status": "success",
        "models": [
            {
                "key": m.key,
                "display_name": m.display_name,
                "provider": m.provider,
                "default": m.key == DEFAULT_MODEL_KEY,
            }
            for m in available_models()
        ],
    }
